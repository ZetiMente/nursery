# Pi Host Adapter

Bare-metal Raspberry Pi deployments. No gateway. The agent *is* the service.

## Status

🐣 **Working profile.** Spawns containers that talk directly to the host.

## Profile defaults

| Key | Value |
|-----|-------|
| Image | `nursery/agent:base` |
| `NURSERY_HOST` | `pi` |
| `NURSERY_OLLAMA_URL` | `http://host.docker.internal:11434` |
| Port publish | `7860:7860` — agent's HTTP reachable from anywhere on the network |
| Memory | `6g` (Pi 4 / 8 GB model default) |
| CPUs | `4.0` (full Pi 4 core count) |

The Pi profile deliberately **publishes the agent's HTTP port** because there's no gateway to route traffic in front of it. `curl http://<pi>:7860/healthz` from your laptop works out of the box.

## Spawning a Pi agent

```bash
uv run nursery spawn examples/agents/pi-layla.yaml

# From another machine on the LAN:
curl http://<pi-ip>:7860/healthz
curl http://<pi-ip>:7860/info
curl -X POST http://<pi-ip>:7860/message \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello"}'
```

## Design notes

- Expects an Ollama daemon **on the Pi itself**. Install with `curl -fsSL https://ollama.com/install.sh | sh`.
- Model weights live in Ollama's cache, shared across agents (if you spawn multiple) on the same Pi.
- No channel integration. Use the HTTP API, or wait for Phase 3 to add channel adapters that can work without a gateway.

## Coming later

- Optional systemd-native mode (no Docker) for resource-constrained devices.
- Local TLS (self-signed or Let's Encrypt via `--acme`) so external access isn't plain HTTP.
- Mount conventions optimized for SD-card wear (move workspace/tmp to an SSD if present).
