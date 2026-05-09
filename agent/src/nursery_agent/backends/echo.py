"""Echo backend — returns a canned reply. Useful for tests and smoke checks."""

from __future__ import annotations

from . import Backend, Message, Reply


class EchoBackend:
    """A trivial backend that echoes the last user message.

    Not useful for actual AI work, but invaluable for proving the plumbing
    works without a model loaded.
    """

    name = "echo"

    def __init__(self, label: str = "echo") -> None:
        self.label = label

    def health(self) -> dict[str, object]:
        return {"ok": True, "model": self.label, "backend": "echo"}

    def chat(self, messages: list[Message]) -> Reply:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        return Reply(
            content=f"[echo:{self.label}] {last_user}",
            thinking=None,
            meta={"backend": "echo"},
        )
