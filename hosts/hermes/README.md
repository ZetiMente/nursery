# Hermes Host Adapter

Nursery agents running alongside a **Hermes Agent** gateway.

[Hermes Agent](https://hermes-agent.nousresearch.com/) is an open-source AI agent framework by [Nous Research](https://nousresearch.com) — a direct sibling of OpenClaw, with persistent memory, autonomous skill creation, and a unified messaging gateway for 15+ platforms (Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email, SMS, Microsoft Teams, and more).

## Status

🐣 **Image shares the base image; profile is ready.** A dedicated `nursery/agent:hermes` image and host-side integration (agent registration with the Hermes gateway, routing channel messages) are follow-up work.

## Profile defaults

| Key | Value |
|-----|-------|
| Image | `nursery/agent:base` (shared with Pi profile for now) |
| `NURSERY_HOST` | `hermes` |
| `NURSERY_GATEWAY_URL` | `http://host.docker.internal:8642` (Hermes API server default) |
| `NURSERY_OLLAMA_URL` | `http://host.docker.internal:11434` |
| Port publish | (none — gateway routes) |
| Memory / CPU | Docker default |

## Prerequisites

Install Hermes on the host first:

```bash
# Linux / macOS / WSL2 / Termux
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# Start the gateway (Telegram / Discord / Slack / etc.)
hermes gateway
```

Hermes installs under `~/.hermes/` (parallel to `~/.openclaw/`). Its API server exposes an **OpenAI-compatible endpoint** on `localhost:8642`, which is what Nursery agents on this profile point at.

## Spawning a Hermes agent

```bash
uv run nursery spawn examples/agents/hermes-layla.yaml
uv run nursery ps
uv run nursery logs layla-hermes --tail 20
```

## Conventions worth knowing

Hermes shares several conventions with OpenClaw that make cross-framework agent authoring easy:

- **`SOUL.md`** for personality — same filename, same idea. A Nursery spec's `soul` field works identically under either host.
- **`agentskills.io`** for portable skills.
- **Workspace-per-agent** directory layout.

This alignment is deliberate — Nous Research and the OpenClaw team both converged on the same patterns. It's good news for Nursery: we can encode these conventions once in the base image and have them work under any host.

## Coming later

- Dedicated `nursery/agent:hermes` Dockerfile (when the integration layer justifies a separate image).
- Host-side adapter that registers Nursery agents with the Hermes gateway so inbound channel messages route to them.
- Shared workspace interop — running the same agent under OpenClaw *or* Hermes by flipping one spec field.

## References

- [Hermes Agent docs](https://hermes-agent.nousresearch.com/docs/)
- [GitHub: NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- [Hermes API server](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server)
