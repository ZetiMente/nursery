# OpenClaw Host Adapter

Runs Nursery agents as containers alongside an existing OpenClaw gateway.

## Status

🐣 Phase 2a: the **container image** (`nursery/agent:openclaw`) exists. See [`../../docker/openclaw/`](../../docker/openclaw/).

The *host-side* adapter (what runs on the OpenClaw gateway and coordinates agents) is not yet implemented. That's the Phase 5 deliverable.

## What exists now (Phase 2a)

- `nursery/agent:openclaw` image: a ready-to-run agent container with OpenClaw-friendly defaults:
  - `NURSERY_HOST=openclaw`
  - `NURSERY_GATEWAY_URL=http://host.docker.internal:7770` (override at runtime)
  - Label `nursery.host=openclaw` so host tooling can filter containers

## What's coming (Phase 5)

- Register agents with the OpenClaw gateway when they spawn
- Route inbound channel messages (Telegram, Discord, Signal, etc.) to the right agent container
- Publish outbound replies back through OpenClaw's channel infrastructure
- Handle OpenClaw-specific conventions (workspaces, session isolation, subagents)

## Running one ad-hoc (Phase 2a)

```bash
# Build (from repo root):
docker/build.sh openclaw

# Run:
docker run --rm -d \
  --name my-agent \
  -p 7860:7860 \
  -v /path/to/spec:/spec:ro \
  -v /path/to/workspace:/workspace \
  -v /path/to/secrets:/run/secrets:ro \
  nursery/agent:openclaw

# Check health:
curl http://localhost:7860/healthz
```

No inference yet — that arrives in Phase 2b. The container will echo any message you POST to `/message`.
