"""Ollama backend — talks to an Ollama daemon over HTTP.

Defaults are tuned for Gemma 4 on constrained hardware (Pi 4):
  - think=True           : let the model reason before answering.
  - num_predict=-1       : unlimited output budget so the model can finish.
  - num_ctx=8192         : generous window without blowing our RAM budget.
  - keep_alive=-1        : stay resident forever; avoid 90-110s cold loads.
  - Gemma sampling:       temperature=1.0, top_p=0.95, top_k=64.

Self-verification (opt-in):
  Inspired by Voyager's iterative prompting loop (Wang et al. 2023,
  https://arxiv.org/abs/2305.16291). When enabled, every chat() runs a
  second inference that critiques the first reply and either approves
  it or rewrites it. Disabled by default because it doubles latency on
  slow hardware; enable with NURSERY_VERIFY=true in the agent's env.

  The verifier runs with think=False and a terse prompt — we want a
  fast judgment, not another deep reasoning trace. Both the original
  and the verified reply are preserved in reply.meta for training-data
  provenance.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from . import Backend, BackendError, Message, Reply

LOG = logging.getLogger("nursery-agent.ollama")

DEFAULT_OLLAMA_URL = "http://host.docker.internal:11434"
DEFAULT_REQUEST_TIMEOUT_S = 15 * 60  # 15 min — Pi 4 + thinking is slow but honest.

# Verification prompt. Intentionally blunt: we want OK or a rewrite, not flattery.
VERIFY_SYSTEM_PROMPT = """You are reviewing a draft reply an assistant just wrote.

Your job is to answer ONE question honestly: does this reply address the user's \
actual message well? Be ruthless, not polite.

If the reply is good, respond with exactly this single word:
OK

If the reply is flawed (wrong, evasive, off-topic, half-answered, sycophantic, \
or ignoring what the user actually said), rewrite it completely and return only \
the rewritten reply. No preamble. No "here's the rewrite." Just the better reply.

Rules:
- Match the persona and voice of the draft.
- Do NOT add disclaimers that weren't asked for.
- Do NOT hedge more than the draft did.
- If the draft was right, say OK. Don't invent problems to justify rewriting."""


@dataclass
class OllamaOptions:
    num_ctx: int = 8192
    num_predict: int = -1
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 64

    def as_dict(self) -> dict[str, Any]:
        return {
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean env var. 'true'/'1'/'yes' (case-insensitive) = True."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


class OllamaBackend:
    """Backend that routes conversations to a running Ollama daemon."""

    name = "ollama"

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        think: bool = True,
        keep_alive: int | str = -1,
        options: OllamaOptions | None = None,
        timeout_s: float = DEFAULT_REQUEST_TIMEOUT_S,
        verify: bool | None = None,
    ) -> None:
        self.model = model
        self.base_url = (base_url or os.environ.get("NURSERY_OLLAMA_URL") or DEFAULT_OLLAMA_URL).rstrip("/")
        self.think = think
        self.keep_alive = keep_alive
        self.options = options or OllamaOptions()
        self.timeout_s = timeout_s
        # Verify: explicit arg > env var > default False.
        self.verify = verify if verify is not None else _env_bool("NURSERY_VERIFY", False)

    # ----- HTTP helpers -----

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read()
        except urllib.error.URLError as e:
            raise BackendError(f"ollama unreachable at {url}: {e}") from e
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise BackendError(f"ollama returned non-JSON: {e}") from e

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                raw = resp.read()
        except urllib.error.URLError as e:
            raise BackendError(f"ollama unreachable at {url}: {e}") from e
        return json.loads(raw.decode("utf-8"))

    # ----- One inference call to Ollama /api/chat -----

    def _inference(
        self,
        messages: list[Message],
        *,
        think: bool,
    ) -> tuple[str, str | None, dict[str, Any]]:
        """Run one chat inference. Returns (content, thinking, meta)."""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "think": think,
            "keep_alive": self.keep_alive,
            "options": self.options.as_dict(),
        }

        resp = self._post("/api/chat", body)

        if "error" in resp:
            raise BackendError(f"ollama error: {resp['error']}")

        msg = resp.get("message") or {}
        content = msg.get("content") or ""
        thinking = msg.get("thinking")

        if not content and not thinking:
            raise BackendError(
                f"ollama returned empty message; done_reason={resp.get('done_reason')!r}"
            )

        meta: dict[str, Any] = {
            "done_reason": resp.get("done_reason"),
            "prompt_eval_count": resp.get("prompt_eval_count"),
            "eval_count": resp.get("eval_count"),
        }
        eval_count = resp.get("eval_count")
        eval_ns = resp.get("eval_duration")
        if isinstance(eval_count, int) and isinstance(eval_ns, int) and eval_ns > 0:
            meta["decode_tok_per_s"] = round(eval_count / (eval_ns / 1e9), 2)

        return content, thinking, meta

    # ----- Self-verification loop -----

    def _verify_and_maybe_rewrite(
        self,
        user_last_message: str,
        draft: str,
        draft_thinking: str | None,
    ) -> tuple[str, dict[str, Any]]:
        """Run the verifier on a draft reply. Returns (final_reply, verify_meta).

        The verifier is asked to respond with literally 'OK' if the draft is
        fine, otherwise a full rewrite. We do not combine — we replace.
        """
        verify_messages: list[Message] = [
            Message(role="system", content=VERIFY_SYSTEM_PROMPT),
            Message(
                role="user",
                content=(
                    f"USER'S ORIGINAL MESSAGE:\n{user_last_message}\n\n"
                    f"ASSISTANT'S DRAFT REPLY:\n{draft}"
                ),
            ),
        ]

        LOG.info("ollama: verifying draft (%d chars)", len(draft))
        verdict, _verdict_thinking, verdict_meta = self._inference(
            verify_messages,
            think=False,  # fast judgment, no deep reasoning trace
        )

        verdict_stripped = verdict.strip()
        ok = verdict_stripped.upper() == "OK" or verdict_stripped.upper().startswith("OK\n")

        if ok:
            LOG.info("ollama: verifier approved draft")
            return draft, {
                "verify_ran": True,
                "verify_verdict": "ok",
                "verify_meta": verdict_meta,
                "original_draft": draft,
                "original_draft_thinking": draft_thinking,
            }

        LOG.info("ollama: verifier rewrote draft (%d → %d chars)", len(draft), len(verdict_stripped))
        return verdict_stripped, {
            "verify_ran": True,
            "verify_verdict": "rewritten",
            "verify_meta": verdict_meta,
            "original_draft": draft,
            "original_draft_thinking": draft_thinking,
        }

    # ----- Backend protocol -----

    def health(self) -> dict[str, object]:
        info: dict[str, object] = {
            "ok": False,
            "model": self.model,
            "backend": "ollama",
            "base_url": self.base_url,
        }
        try:
            tags = self._get("/api/tags")
        except BackendError as e:
            info["error"] = str(e)
            return info

        info["ok"] = True
        present = [m.get("name") for m in tags.get("models", [])]
        info["model_present"] = self.model in present
        info["models_available"] = present
        info["think"] = self.think
        info["keep_alive"] = self.keep_alive
        info["verify"] = self.verify
        info["options"] = self.options.as_dict()
        return info

    def chat(self, messages: list[Message]) -> Reply:
        LOG.info(
            "ollama: chat model=%s messages=%d think=%s verify=%s",
            self.model, len(messages), self.think, self.verify,
        )

        # Primary inference
        content, thinking, draft_meta = self._inference(messages, think=self.think)

        meta: dict[str, Any] = {
            "backend": "ollama",
            "model": self.model,
            **draft_meta,
        }

        LOG.info(
            "ollama: reply done_reason=%s output_tokens=%s decode=%s tok/s",
            meta.get("done_reason"),
            meta.get("eval_count"),
            meta.get("decode_tok_per_s"),
        )

        if not self.verify:
            return Reply(content=content, thinking=thinking, meta=meta)

        # Self-verification pass
        user_last = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        final_content, verify_meta = self._verify_and_maybe_rewrite(
            user_last_message=user_last,
            draft=content,
            draft_thinking=thinking,
        )
        meta.update(verify_meta)

        # Thinking stays from the original; the rewritten reply doesn't have its own trace.
        return Reply(content=final_content, thinking=thinking, meta=meta)
