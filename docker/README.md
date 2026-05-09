# Docker

Base images and Dockerfiles for Nursery agents.

## Planned Images

- **`nursery/agent:base`** — minimal runtime with Python + inference client abstraction. No opinions about personality or channels.
- **`nursery/agent:openclaw`** — base + OpenClaw-specific protocol adapter.
- **`nursery/agent:hermes`** — base + Hermes adapter.
- **`nursery/agent:pi`** — slim build targeting ARM/Pi hardware constraints.

## Design Notes

- Images should be **layer-cached aggressively**. Base → host adapter → agent-specific config.
- Agents are **not** built per-individual. The image is generic; the individual is a workspace + spec.
- Model clients (Anthropic, Google, local Llama, etc.) live in the base image behind a shared interface.
- Secrets are **never** baked in. They mount at runtime.

## Status

No Dockerfiles yet. See [`../docs/architecture.md`](../docs/architecture.md) for the shape we're heading toward.
