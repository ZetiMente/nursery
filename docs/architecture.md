# Architecture

This document captures the shape of Nursery as it's being designed. It will evolve.

## Layers

```
┌──────────────────────────────────────────┐
│  User                                    │
└──────────────┬───────────────────────────┘
               │ agent.yaml
               ▼
┌──────────────────────────────────────────┐
│  Nursery CLI                             │
│  (validate spec → call host adapter)     │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  Host Adapter (OpenClaw / Hermes / Pi)   │
│  (register agent, wire channels)         │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  Container Runtime (Docker)              │
│  (pull image, mount workspace, start)    │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  Agent Process                           │
│  ├─ loads SOUL.md + workspace            │
│  ├─ connects to channels                 │
│  ├─ reads secrets from mount             │
│  └─ speaks host protocol                 │
└──────────────────────────────────────────┘
```

## Agent Lifecycle

1. **Spawn** — CLI reads spec, host adapter registers the agent, container starts.
2. **Running** — Agent receives messages, thinks, replies, persists memory.
3. **Stop** — Container killed. Workspace preserved on host.
4. **Respawn** — Same spec + workspace = same agent, new body.
5. **Fork** — New individual spawned from a blueprint, with a fresh workspace.
6. **Remove** — Container and workspace both destroyed. Identity is gone.

## What Lives Where

| Thing            | Lives In           | Survives Respawn? |
|------------------|--------------------|-----|
| SOUL.md          | Workspace volume   | ✅   |
| Memory files     | Workspace volume   | ✅   |
| Secrets          | Secrets mount      | ✅   |
| Running state    | Container memory   | ❌   |
| Spec file        | Host filesystem    | ✅   |
| Image            | Docker daemon      | ✅   |

## Further Reading

- [`protocol.md`](./protocol.md) — agent ↔ host gateway protocol
- [`secrets.md`](./secrets.md) — how secrets are stored and scoped
- [`identity.md`](./identity.md) — what makes an agent "itself"
