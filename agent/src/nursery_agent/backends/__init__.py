"""Nursery agent backends — pluggable inference runtimes.

A Backend takes a list of messages (including a system message derived
from the agent's soul) and returns a reply. Concrete backends wrap
specific runtimes: Ollama for local models, future ones for cloud APIs.

The abstraction is intentionally small. Phase 2b does not try to unify
streaming, tools, or multimodal across backends — that comes later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class Reply:
    content: str
    thinking: str | None = None
    # Optional performance / provenance metadata — keys are backend-specific.
    meta: dict[str, object] = field(default_factory=dict)


class BackendError(RuntimeError):
    """Raised when a backend cannot produce a reply."""


class Backend(Protocol):
    """The contract every backend honors.

    Implementations must be synchronous for Phase 2b. Streaming and async
    arrive in a later phase; their absence is intentional to keep the
    first implementation small and testable.
    """

    name: str

    def health(self) -> dict[str, object]:
        """Return a dict describing backend status. Must not raise.

        Keys by convention: 'ok' (bool), 'model' (str), plus free-form
        backend-specific metadata.
        """
        ...

    def chat(self, messages: list[Message]) -> Reply:
        """Run a single conversation turn and return the reply.

        Should raise BackendError on any unrecoverable problem.
        """
        ...


def resolve_backend(model: str, **kwargs: object) -> Backend:
    """Construct a backend from a spec's 'model' string.

    Format: '<provider>/<model>'
      ollama/batiai/gemma4-e2b:q4     -> OllamaBackend(model='batiai/gemma4-e2b:q4')
      echo/anything                   -> EchoBackend()
    """
    if "/" not in model:
        raise BackendError(f"invalid model string {model!r}; expected '<provider>/<name>'")
    provider, _, name = model.partition("/")

    if provider == "echo":
        from .echo import EchoBackend
        return EchoBackend(label=name or "echo")

    if provider == "ollama":
        if not name:
            raise BackendError("ollama backend requires a model name after 'ollama/'")
        from .ollama import OllamaBackend
        return OllamaBackend(model=name, **kwargs)  # type: ignore[arg-type]

    raise BackendError(f"unknown backend provider {provider!r}")
