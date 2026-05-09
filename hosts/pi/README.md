# Pi Host Adapter

Bare-metal Raspberry Pi deployments, no gateway framework required.

## Goals

- Run Nursery agents on a Pi 4/5 with minimal overhead
- No dependency on OpenClaw or Hermes — a Pi can be its own tiny gateway
- Respect resource constraints (RAM, CPU, SD card wear)
- Prefer efficient models (local Llama, small API models) by default

## Design Notes

- Docker on Pi works but adds overhead. Alternative: systemd services + lightweight sandboxing (bubblewrap, firejail).
- Agents on a Pi will likely share a single channel connection (e.g. one Telegram bot) and multiplex.
- SD card longevity: workspaces should live on a mounted SSD/USB when possible.

## Status

🥚 Not implemented.
