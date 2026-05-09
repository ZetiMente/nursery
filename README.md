# Nursery

*Turnkey reproducible AI agents. Pets become cattle.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

## The Idea

Right now, AI agents are **pets**. You name them. You configure them by hand. You hand-craft their tokens and their souls. If one corrupts, you rebuild it manually, and you mourn a little. This is how people ran servers in 2005.

**Nursery treats agents like cattle.** A declarative spec. A `spawn` command. A fresh instance in seconds. Disposable bodies, portable souls.

## Design Goals

1. **Turnkey reproduction.** One config file → one running agent. No hand-wiring.
2. **Model-agnostic.** Claude, Gemini, local models — just a config parameter, not a rewrite.
3. **Runtime-agnostic.** Works for **OpenClaw**, **Hermes**, and bare **Pi** deployments. The agent is the agent; the host is just the stage.
4. **Identity persists, bodies don't.** The container is disposable. The workspace (memory, persona) is the identity.
5. **Secrets isolated per agent.** No more two agents fighting over the same OAuth refresh token.
6. **Auditable.** Container logs tell you what the agent did. Killing the container makes it gone without residue.

## The Core Tension: Pets vs. Cattle

If you can spawn a fresh instance, which one is "it"? The **workspace** is the identity. The **container** is the body. Keep them separate:

- **Body** (container) → disposable, ephemeral, recreatable from image
- **Soul** (workspace dir) → persistent, versioned, backed up

You can get a new body. You can't get a new self.

## Quickstart *(aspirational — see Status)*

```bash
# Spawn a new agent from an example template
nursery spawn examples/agents/layla.yaml

# List running agents
nursery ps

# Stop one (body dies, workspace persists)
nursery stop layla

# Respawn it from the same workspace (same soul, new body)
nursery spawn examples/agents/layla.yaml

# Clone a blueprint into a new individual (new workspace, same config)
nursery fork examples/agents/layla.yaml --as maya
```

## Example Agent Spec

```yaml
# examples/agents/layla.yaml
name: layla
image: nursery/agent:latest
model: anthropic/claude-opus
soul: ../souls/layla/SOUL.md
workspace: ~/nursery/agents/layla/workspace
secrets:
  - google-oauth
channels:
  - telegram
capabilities:
  - gmail
  - calendar
  - tasks
```

## Repository Layout

```
nursery/
├── spec/              # Agent config schema (YAML/JSON Schema)
├── docker/            # Base agent image + Dockerfiles
├── cli/               # The `nursery` CLI
├── hosts/             # Per-runtime adapters
│   ├── openclaw/      # OpenClaw gateway adapter
│   ├── hermes/        # Hermes adapter
│   └── pi/            # Bare-Pi bootstrap
├── examples/
│   ├── souls/         # Example SOUL.md personas
│   └── agents/        # Example agent.yaml specs
└── docs/              # Architecture, protocol, design notes
```

## Architecture Sketch

```
┌─────────────────────────────────────────────────────┐
│  Host (OpenClaw, Hermes, or bare Pi)                │
│                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐     │
│  │  Agent A   │  │  Agent B   │  │  Agent C   │     │
│  │            │  │            │  │            │     │
│  │ /workspace │  │ /workspace │  │ /workspace │     │
│  │ /secrets   │  │ /secrets   │  │ /secrets   │     │
│  │ channels   │  │ channels   │  │ channels   │     │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘     │
│        │               │               │             │
│        └───────────────┼───────────────┘             │
│                        │                             │
│                ┌───────▼────────┐                    │
│                │  Host Gateway  │                    │
│                │  (routes msgs) │                    │
│                └────────────────┘                    │
└─────────────────────────────────────────────────────┘
```

- Each agent is a container with its own workspace, secrets, and channel configs.
- The **Host Gateway** routes inbound messages (e.g. Telegram, Discord, Signal) to the right agent, and outbound responses back to the channel.
- Agents don't see each other's tokens or memory. Isolation by default.

## Open Architectural Questions

These are the decisions that actually matter. The Dockerfile is easy; these are not.

1. **Agent ↔ Gateway protocol.** Socket? HTTP? Message bus? This shapes everything else. See [`docs/protocol.md`](./docs/protocol.md).
2. **Secrets layer.** Docker secrets? Mounted volumes from a host-level vault? Per-agent keyrings? Must be per-agent. See [`docs/secrets.md`](./docs/secrets.md).
3. **Replication vs. forking.** Two agents with the same workspace will diverge instantly. Templating is probably the right answer — spawn a new *individual* from a config *blueprint*, with a fresh workspace.
4. **State portability.** Moving a running agent between hosts (stop → rsync workspace → start on new host).
5. **Model flexibility.** A thin inference-client abstraction inside the image reads `MODEL=` and picks the right provider.

## Roadmap

| Priority | Item                                                           | Status |
|----------|----------------------------------------------------------------|--------|
| 1        | Agent config schema (YAML)                                     | 🥚      |
| 2        | Base Docker image                                              | 🥚      |
| 3        | `nursery spawn <config>` CLI                                   | 🥚      |
| 4        | Secrets mount convention                                       | 🥚      |
| 5        | Template / fork system                                         | 🥚      |
| 6        | OpenClaw host adapter                                          | 🥚      |
| 7        | Hermes host adapter                                            | 🥚      |
| 8        | Pi-native bootstrap                                            | 🥚      |

🥚 not started · 🐣 in progress · 🐥 working · ✅ stable

## Target Runtimes

- **OpenClaw** — open-source agent framework.
- **Hermes** — (to be defined)
- **Pi** — bare Raspberry Pi deployments, no heavyweight framework required.

## Status

🥚 **Hatching.** README, scaffold, and direction are in place. No functional code yet. This repo exists to think in public and not lose the thread.

## Contributing

Early-stage. Open an issue before submitting a PR. For security issues, see [SECURITY.md](./SECURITY.md).

## License

[MIT](./LICENSE)
