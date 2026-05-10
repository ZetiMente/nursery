# Standalone Host Adapter

Thin Nursery runtime. **No external gateway framework.** The agent is the service.

Runs on any Linux — Raspberry Pi hardware, WSL, a laptop, or an EC2 instance. Nothing in this profile is hardware-specific.

## Status

🐣 **Working profile.** Spawns containers that run the agent as a standalone HTTP service reachable on the host.

## Profile defaults

| Key | Value |
|-----|-------|
| Image | `nursery/agent:base` |
| `NURSERY_HOST` | `standalone` |
| `NURSERY_OLLAMA_URL` | `http://host.docker.internal:11434` |
| Port publish | `7860:7860` — agent's HTTP reachable from anywhere on the network |
| Memory | `6g` (comfortable for Gemma 4 E2B Q4 on a 7-8 GB host) |
| CPUs | `4.0` (tune down for smaller hosts) |

This profile **publishes the agent's HTTP port** because there's no gateway to route traffic in front of it. `curl http://<host>:7860/healthz` from your laptop works out of the box.

## Use this for

- **Bare-metal** single-host deployments (Pi, home server, etc.)
- **WSL "server" style** development on Windows
- **Cloud VMs** — AWS EC2, Hetzner, Fly, etc.
- Any case where there's no OpenClaw / Hermes / Pi gateway above you

## Spawning a standalone agent

```bash
uv run nursery spawn examples/agents/standalone-layla.yaml

# From another machine on the network:
curl http://<host-ip>:7860/healthz
curl http://<host-ip>:7860/info
curl -X POST http://<host-ip>:7860/message \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello"}'
```

## Design notes

- Expects an **Ollama daemon on the host itself**. Install with `curl -fsSL https://ollama.com/install.sh | sh`.
- Model weights live in Ollama's cache, shared across agents on the same host.
- No channel integration. Use the HTTP API, or wait for Phase 3 to add channel adapters that don't need a gateway.
- For cloud deployments (e.g. AWS turnkey), this is the profile that gets used. See the (future) `hosts/standalone/aws.md` for the planned AWS quickstart.

## Coming later

- **Multi-arch images** (`linux/amd64` + `linux/arm64`) so the same tag runs on a Pi and on a cloud VM.
- **AWS turnkey launch** — `nursery aws launch` provisions an EC2, installs prerequisites, spawns the agent.
- Optional systemd-native mode (no Docker) for resource-constrained or locked-down environments.
- Local TLS (self-signed or ACME) so external access isn't plain HTTP.
