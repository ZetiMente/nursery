"""Entry point for the Nursery agent container.

Responsibilities (Phase 2a):
  1. Read the agent spec from /spec/agent.yaml (path overridable).
  2. Read the soul (persona) from the path in the spec.
  3. Verify the workspace is mounted read/write.
  4. Verify secrets directory is mounted (read-only is not enforced here;
     we trust the host).
  5. Start an HTTP server on 0.0.0.0:$NURSERY_AGENT_PORT with:
       GET /healthz   → {"ok": true, "name": ..., "model": ...}
       GET /info      → spec metadata (no secret values)
       POST /message  → echoes the message back (placeholder for Phase 2b)

No inference yet. This is a skeleton — enough to prove the container boots,
reads its spec, and can accept messages. Phase 2b wires a real model in.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

LOG = logging.getLogger("nursery-agent")

DEFAULT_SPEC_PATH = "/spec/agent.yaml"
DEFAULT_PORT = 7860
DEFAULT_WORKSPACE = "/workspace"
DEFAULT_SECRETS_DIR = "/run/secrets"


# --------------------------------------------------------------------------
# Spec loading
# --------------------------------------------------------------------------


def _load_spec(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"agent: spec not found at {path}")

    try:
        import yaml  # type: ignore
    except ImportError:
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text())
        raise SystemExit("agent: PyYAML not installed and spec is not JSON")

    with path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    if not isinstance(spec, dict):
        raise SystemExit("agent: spec must be a mapping")

    return spec


def _resolve_soul(spec: dict[str, Any], spec_path: Path) -> str | None:
    """Return the contents of the soul file, or None if no soul specified."""
    soul_ref = spec.get("soul")
    if not soul_ref:
        return None

    soul_path = Path(soul_ref)
    if not soul_path.is_absolute():
        soul_path = (spec_path.parent / soul_ref).resolve()

    if not soul_path.exists():
        LOG.warning("agent: soul file not found at %s — continuing without", soul_path)
        return None

    return soul_path.read_text(encoding="utf-8")


def _check_workspace(workspace: str) -> None:
    p = Path(workspace)
    if not p.exists():
        raise SystemExit(f"agent: workspace {workspace} does not exist (must be mounted)")
    if not p.is_dir():
        raise SystemExit(f"agent: workspace {workspace} is not a directory")
    # Sanity check: can we write?
    try:
        test = p / ".nursery-write-test"
        test.write_text("ok")
        test.unlink()
    except OSError as e:
        raise SystemExit(f"agent: workspace {workspace} not writable: {e}") from None


def _list_secrets(secrets_dir: str) -> list[str]:
    p = Path(secrets_dir)
    if not p.exists():
        return []
    return sorted(child.name for child in p.iterdir() if child.is_file())


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------


class _State:
    spec: dict[str, Any]
    soul: str | None
    secrets: list[str]
    workspace: str


STATE = _State()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        LOG.info("%s %s", self.address_string(), fmt % args)

    def _json(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._json(200, {
                "ok": True,
                "name": STATE.spec.get("name"),
                "model": STATE.spec.get("model"),
            })
            return
        if self.path == "/info":
            self._json(200, {
                "name": STATE.spec.get("name"),
                "image": STATE.spec.get("image"),
                "model": STATE.spec.get("model"),
                "channels": STATE.spec.get("channels", []),
                "capabilities": STATE.spec.get("capabilities", []),
                "workspace": STATE.workspace,
                "soul_loaded": STATE.soul is not None,
                "soul_bytes": len(STATE.soul) if STATE.soul else 0,
                "secrets_mounted": STATE.secrets,
            })
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/message":
            self._json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError as e:
            self._json(400, {"error": f"invalid json: {e}"})
            return

        # Phase 2a placeholder: echo + metadata. Phase 2b will route to a model.
        self._json(200, {
            "ok": True,
            "agent": STATE.spec.get("name"),
            "received": body,
            "note": "Phase 2a: echo-only. No inference yet.",
        })


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def _install_signal_handlers(server: ThreadingHTTPServer) -> None:
    def shutdown(signum: int, _frame: Any) -> None:
        LOG.info("agent: received signal %d, shutting down", signum)
        server.shutdown()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    spec_path = Path(os.environ.get("NURSERY_SPEC_PATH", DEFAULT_SPEC_PATH))
    workspace = os.environ.get("NURSERY_WORKSPACE", DEFAULT_WORKSPACE)
    secrets_dir = os.environ.get("NURSERY_SECRETS_DIR", DEFAULT_SECRETS_DIR)
    port = int(os.environ.get("NURSERY_AGENT_PORT", str(DEFAULT_PORT)))

    LOG.info("agent: starting (spec=%s workspace=%s port=%d)", spec_path, workspace, port)

    spec = _load_spec(spec_path)
    soul = _resolve_soul(spec, spec_path)
    _check_workspace(workspace)
    secrets = _list_secrets(secrets_dir)

    STATE.spec = spec
    STATE.soul = soul
    STATE.secrets = secrets
    STATE.workspace = workspace

    LOG.info(
        "agent: ready — name=%s model=%s soul=%s secrets=%s",
        spec.get("name"), spec.get("model"),
        "yes" if soul else "no",
        secrets or "none",
    )

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)  # noqa: S104
    _install_signal_handlers(server)

    LOG.info("agent: listening on 0.0.0.0:%d", port)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        LOG.info("agent: stopped")

    return 0


if __name__ == "__main__":
    sys.exit(main())
