# Docker

Base images and Dockerfiles for Nursery agents.

## Images

| Image                         | Purpose                                            | Status |
|-------------------------------|----------------------------------------------------|--------|
| `nursery/agent:base`          | Minimal generic runtime. Host-agnostic.            | 🐣 (Phase 2a) |
| `nursery/agent:openclaw`      | `FROM base` + OpenClaw-specific defaults.          | 🐣 (Phase 2a) |
| `nursery/agent:hermes`        | `FROM base` + Hermes adapter.                      | 🥚      |
| `nursery/agent:pi`            | Slim build for Pi / edge.                          | 🥚      |

## Layout

```
docker/
├── base/
│   └── Dockerfile        # nursery/agent:base
├── openclaw/
│   └── Dockerfile        # nursery/agent:openclaw (FROM base)
└── build.sh              # one-shot build script
```

## Building

```bash
# Build both base and openclaw:
docker/build.sh

# Just one:
docker/build.sh base
docker/build.sh openclaw

# Use a different registry/prefix:
NURSERY_REGISTRY=ghcr.io/zetimente/nursery docker/build.sh

# Build and push (requires docker login):
docker/build.sh --push
```

## Runtime Conventions

Every Nursery agent container expects:

| Mount / Env          | Path                    | Purpose                                     |
|----------------------|-------------------------|---------------------------------------------|
| Spec file            | `/spec/agent.yaml`      | Mounted read-only by the host.              |
| Workspace            | `/workspace`            | Agent's persistent state. Read/write.       |
| Secrets              | `/run/secrets/`         | Mounted read-only by the host. Per-agent.   |
| Port                 | `$NURSERY_AGENT_PORT`   | Default `7860`. HTTP server.                |

## Environment Variables

| Variable                   | Default                          | Description                           |
|----------------------------|----------------------------------|---------------------------------------|
| `NURSERY_SPEC_PATH`        | `/spec/agent.yaml`               | Where to read the spec from.          |
| `NURSERY_WORKSPACE`        | `/workspace`                     | Workspace mount point.                |
| `NURSERY_SECRETS_DIR`      | `/run/secrets`                   | Secrets mount point.                  |
| `NURSERY_AGENT_PORT`       | `7860`                           | HTTP server port inside container.    |
| `NURSERY_HOST`             | (unset) / `openclaw` (openclaw)  | Host type. Hints adapter behavior.    |
| `NURSERY_GATEWAY_URL`      | (unset) / OpenClaw default       | Gateway to talk back to.              |
| `LOG_LEVEL`                | `INFO`                           | `DEBUG`, `INFO`, `WARNING`, `ERROR`.  |

## HTTP API (Phase 2a)

The running container exposes:

```
GET  /healthz    → {"ok": true, "name": ..., "model": ...}
GET  /info       → spec metadata (no secret values)
POST /message    → echoes the message (Phase 2a placeholder)
```

Real inference arrives in Phase 2b.

## Design Notes

- **Layered images.** `base` is the shared runtime; per-host images layer on top. Keeps build cache efficient.
- **Non-root user.** Container runs as `nursery` (UID 1000) for bind-mount safety.
- **Tini as PID 1.** Proper signal forwarding and zombie reaping.
- **Secrets never baked.** Images are build-time-deterministic. Secrets arrive only at run time via mount.
- **Model clients not in base.** Keeps the base small; Phase 2b adds them behind a shared interface.
