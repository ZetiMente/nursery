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

Nursery grows in phases. Each phase has one goal: prove the next layer works before stacking on it.

Legend: 🥚 not started · 🐣 in progress · 🐥 working · ✅ stable

### Phase 0 — Hatching 🐣

*The idea exists. This repo exists. The thesis is written down.*

- [x] Write the README
- [x] Scaffold the directory structure
- [x] MIT license + SECURITY.md
- [x] Architecture / protocol / secrets / identity notes
- [ ] Decide the agent ↔ host protocol (see [`docs/protocol.md`](./docs/protocol.md))

**Done when:** the design is coherent enough to build against.

---

### Phase 1 — First Breath 🐥

*An agent spec exists and can be validated.*

- [x] Write the agent config JSON Schema (`spec/agent.schema.json`)
- [x] `nursery validate <spec.yaml>` — lints a spec file
- [x] At least one real example spec that passes validation

**Done when:** you can write `agent.yaml` and the tool tells you if it's valid. ✓

---

### Phase 2 — First Spawn 🥚

*One agent spawns from a spec and runs in a container. End-to-end on localhost.*

- [ ] Base Docker image (`nursery/agent:base`)
- [ ] Model abstraction: container reads `MODEL=` and picks a provider
- [ ] `nursery spawn <spec.yaml>` — builds (if needed), mounts workspace, starts container
- [ ] `nursery ps` / `nursery stop` / `nursery logs`
- [ ] Agent can read its SOUL.md and workspace from the mounted volume

**Done when:** `nursery spawn example.yaml` brings up a containerized agent that loads its own soul.

---

### Phase 3 — First Conversation 🥚

*An agent receives a message, thinks, and replies. One channel, one agent.*

- [ ] Host gateway process (routes messages between channels and agents)
- [ ] Agent ↔ gateway protocol implemented (decision made in Phase 0)
- [ ] Telegram channel adapter
- [ ] Agent state persistence (memory survives respawn)

**Done when:** you can message a Nursery agent on Telegram and get a reply.

---

### Phase 4 — First Swarm 🥚

*Two agents running side-by-side with full isolation. The Layla/Lola problem solved.*

- [ ] Per-agent secrets directory, mounted read-only, scoped to one container
- [ ] Gateway routes messages to the right agent by name/channel
- [ ] Cross-agent access is impossible by design (verify with a test)
- [ ] Agent A crashing does not affect Agent B

**Done when:** two agents with different OAuth tokens and personas coexist without stepping on each other.

---

### Phase 5 — First Host 🥚

*Nursery runs inside OpenClaw.*

- [ ] OpenClaw host adapter (`hosts/openclaw/`)
- [ ] Migration path for an existing OpenClaw agent → Nursery spec
- [ ] Documented setup for running Nursery on a Pi inside OpenClaw

**Done when:** Layla and Lola both run as Nursery agents inside OpenClaw.

---

### Phase 6 — First Wild 🥚

*Nursery runs outside OpenClaw's ecosystem.*

- [ ] Hermes host adapter (`hosts/hermes/`)
- [ ] Pi-native bootstrap (`hosts/pi/`) — no heavyweight framework required
- [ ] A single agent portable across all three hosts without code changes

**Done when:** the same agent spec runs on OpenClaw, Hermes, and a bare Pi.

---

### Phase 7 — First Fork 🥚

*Templates and forks. New individuals from blueprints.*

- [ ] `nursery fork <spec> --as <name>` creates a new individual (new workspace, same config)
- [ ] Clear semantics for what's shared vs. unique (the identity problem)
- [ ] Documentation and examples of intentional replication

**Done when:** you can mass-produce agents from a template without any of them sharing identity.

---

### Phase ∞ — Horizon 🥚

*Open-ended directions once the foundation is solid.*

- Replication across hosts (move a running agent, preserve state)
- Vaulted secret backends (HashiCorp Vault, age-encrypted files)
- Local model integration (Llama, Gemma, others)
- Multi-channel agents (one agent, many bots)
- Agent-to-agent messaging (careful — see [`docs/identity.md`](./docs/identity.md))
- Resource quotas, rate limiting, graceful degradation
- Observability (metrics, traces, health endpoints)
- A clean story for migrating / backing up workspaces

No promises. These live here so they don't get lost.

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
