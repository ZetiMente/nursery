# Hermes Host Adapter

Nursery agents running under a **Hermes** gateway.

## Status

🥚 **Provisional.** The Hermes host profile is a placeholder with reasonable defaults until the design is fleshed out.

## What "Hermes" means here

Today, Hermes is a *name reservation* for a non-OpenClaw gateway design. The profile's defaults are copied from OpenClaw with two deliberate tweaks:

1. Different default gateway port (`7771` instead of `7770`) so the two don't collide.
2. `NURSERY_HOST=hermes` so agents can branch on their host at runtime if needed.

**If Hermes has specific conventions we should encode** (authentication, message schema, resource expectations), that should land here as a proper profile rather than these placeholders.

## Profile defaults (provisional)

| Key | Value |
|-----|-------|
| Image | `nursery/agent:base` (no dedicated Hermes image yet) |
| `NURSERY_HOST` | `hermes` |
| `NURSERY_GATEWAY_URL` | `http://host.docker.internal:7771` |
| `NURSERY_OLLAMA_URL` | `http://host.docker.internal:11434` |
| Port publish | (none — assumes gateway routes) |
| Memory / CPU | Docker default |

Spawning an agent against this profile prints a `note: host profile 'hermes' is PROVISIONAL` warning so no one forgets.

## Spawning

```bash
uv run nursery spawn examples/agents/hermes-layla.yaml
```

## What's needed to move this out of provisional

- A concrete definition of what Hermes actually is (gateway? mesh? protocol?).
- A dedicated `docker/hermes/Dockerfile`, or a clear justification that `base` is enough.
- Specified auth model, channel conventions, and agent registration protocol.
- An end-to-end smoke test.

Until then, this profile works (agents spawn, run, respond to local HTTP), but nothing coordinates them across Hermes-native channels.
