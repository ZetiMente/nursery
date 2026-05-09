"""Ollama backend — talks to an Ollama daemon over HTTP.

Defaults are tuned for Gemma 4 on constrained hardware (Pi 4):
  - think=True           : let the model reason before answering.
  - num_predict=-1       : unlimited output budget so the model can finish.
  - num_ctx=8192         : generous window without blowing our RAM budget.
  - keep_alive=-1        : stay resident forever; avoid 90-110s cold loads.
  - Gemma sampling:       temperature=1.0, top_p=0.95, top_k=64.

These defaults can be overridden per-agent via the spec's 'environment'
block or 'model_options' (future extension).
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
    ) -> None:
        self.model = model
        self.base_url = (base_url or os.environ.get("NURSERY_OLLAMA_URL") or DEFAULT_OLLAMA_URL).rstrip("/")
        self.think = think
        self.keep_alive = keep_alive
        self.options = options or OllamaOptions()
        self.timeout_s = timeout_s

    # ----- helpers -----

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

    # ----- Backend protocol -----

    def health(self) -> dict[str, object]:
        info: dict[str, object] = {"ok": False, "model": self.model, "backend": "ollama", "base_url": self.base_url}
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
        info["options"] = self.options.as_dict()
        return info

    def chat(self, messages: list[Message]) -> Reply:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "options": self.options.as_dict(),
        }

        LOG.info(
            "ollama: chat model=%s messages=%d think=%s",
            self.model, len(messages), self.think,
        )

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

        meta: dict[str, object] = {
            "backend": "ollama",
            "model": self.model,
            "done_reason": resp.get("done_reason"),
            "prompt_eval_count": resp.get("prompt_eval_count"),
            "eval_count": resp.get("eval_count"),
        }
        # Decode rate (tok/s) when we have the data
        eval_count = resp.get("eval_count")
        eval_ns = resp.get("eval_duration")
        if isinstance(eval_count, int) and isinstance(eval_ns, int) and eval_ns > 0:
            meta["decode_tok_per_s"] = round(eval_count / (eval_ns / 1e9), 2)

        LOG.info(
            "ollama: reply done_reason=%s output_tokens=%s decode=%s tok/s",
            meta.get("done_reason"), meta.get("eval_count"), meta.get("decode_tok_per_s"),
        )

        return Reply(content=content, thinking=thinking, meta=meta)
