# Nursery

*Turnkey reproducible AI agents. Pets become cattle.*

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

If you can spawn a fresh instance of an agent, which one is "it"? The **workspace** is the identity. The **container** is the body. Keep them separate:

- Body (container) → disposable, ephemeral, recreatable from image
- Soul (workspace dir) → persistent, versioned, backed up

This mirrors the human/body metaphor. You can get a new body. You can't get a new self.

## Example Agent Spec

```yaml
# agent.yaml
name: example-agent
image: nursery/agent:latest
model: anthropic/claude-opus
soul: ./souls/example/SOUL.md
workspace: ~/agents/example/workspace
secrets:
  - google-oauth
channels:
  - telegram
capabilities:
  - gmail
  - calendar
  - tasks
```

```bash
nursery spawn agent.yaml
# → pulls image, mounts workspace, loads secrets, connects to channel
# → agent is alive
```

## Architecture Sketch

```
┌─────────────────────────────────────────────────────┐
│  Host (OpenClaw, Hermes, or bare Pi)                │
│                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │  Agent A   │  │  Agent B   │  │  Agent C   │   │
│  │            │  │            │  │            │   │
│  │ /workspace │  │ /workspace │  │ /workspace │   │
│  │ /secrets   │  │ /secrets   │  │ /secrets   │   │
│  │ channels   │  │ channels   │  │ channels   │   │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘   │
│        │               │               │           │
│        └───────────────┼───────────────┘           │
│                        │                           │
│                ┌───────▼────────┐                  │
│                │  Host Gateway  │                  │
│                │  (routes msgs) │                  │
│                └────────────────┘                  │
└─────────────────────────────────────────────────────┘
```

- Each agent is a container with its own workspace, secrets, and channel configs.
- The **Host Gateway** routes inbound messages (e.g. Telegram, Discord, Signal) to the right agent, and outbound responses back to the channel.
- Agents don't see each other's tokens or memory. Isolation by default.

## Open Architectural Questions

These are the decisions that actually matter. The Dockerfile is easy; these are not.

1. **Agent ↔ Gateway protocol.** How does a containerized agent receive messages and publish replies? Socket? HTTP? Message bus?
2. **Secrets layer.** Docker secrets? Mounted volumes from a host-level vault? Per-agent keyrings? Must be per-agent — the "shared OAuth refresh token" problem is real.
3. **Replication vs. forking.** If you clone an agent with the same workspace, two instances with the same memory will diverge instantly. Templating (spawn a *new individual* from a *blueprint* with a fresh workspace) is probably the right answer.
4. **State portability.** Can you move a running agent from a Pi to a bigger box? (Probably: stop container → rsync workspace → start on new host.)
5. **Model flexibility.** A thin inference-client abstraction inside the image reads `MODEL=` and picks the right provider.

## Roadmap

| Priority | Item |
|----------|------|
| 1 | Agent config schema (YAML) |
| 2 | Base Docker image |
| 3 | `nursery spawn <config>` CLI |
| 4 | Secrets mount convention |
| 5 | Template system (spawn N instances from one template with unique workspaces) |
| 6 | OpenClaw host adapter |
| 7 | Hermes host adapter |
| 8 | Pi-native bootstrap |

## Target Runtimes

- **OpenClaw** — open-source agent framework.
- **Hermes** — (to define)
- **Pi** — bare Raspberry Pi deployments, no heavyweight framework required.

## Status

🥚 **Hatching.** Just the idea + this README. No code yet. This repo exists to think in public and not lose the thread.

## Contributing

Early-stage. Issues and discussion welcome. Code contributions: please open an issue to discuss before submitting a PR.

For security issues, see [SECURITY.md](./SECURITY.md).

## License

[MIT](./LICENSE)
