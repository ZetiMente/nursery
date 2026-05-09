# OpenClaw Host Adapter

Nursery agents running alongside an existing OpenClaw gateway.

## Status

🐣 **Image available. Host-side adapter still Phase 5.**

- `nursery/agent:openclaw` image exists — see [`../../docker/openclaw/`](../../docker/openclaw/).
- `HostProfile` defaults are in place (see [`../../cli/src/nursery_cli/lifecycle.py`](../../cli/src/nursery_cli/lifecycle.py)).
- The actual gateway-side integration (announcing agents, routing channel messages, etc.) is **Phase 5**.

## Profile defaults

| Key | Value |
|-----|-------|
| Image | `nursery/agent:openclaw` |
| `NURSERY_HOST` | `openclaw` |
| `NURSERY_GATEWAY_URL` | `http://host.docker.internal:7770` |
| `NURSERY_OLLAMA_URL` | `http://host.docker.internal:11434` |
| Port publish | (none — gateway routes) |
| Memory / CPU | Docker default (no host-profile cap) |

## Spawning an OpenClaw agent

```bash
# From the repo root:
uv run nursery spawn examples/agents/openclaw-layla.yaml

# Verify:
uv run nursery ps
uv run nursery logs layla-openclaw --tail 20
```

The container runs as `nursery-layla-openclaw`, labeled `nursery.host=openclaw`.

## Coming in Phase 5

- Register agents with the OpenClaw gateway on spawn.
- Route inbound channel messages (Telegram, Discord, Signal, …) to the right agent container.
- Publish outbound replies back through OpenClaw's channel infrastructure.
- Handle OpenClaw-specific conventions (workspaces, session isolation, subagents).
