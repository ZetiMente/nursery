# Host Adapters

A **host** is the environment an agent runs inside. Each host has its own gateway, channel plumbing, and conventions — and Nursery should work across all of them without agents caring which one they're on.

## Supported Hosts

| Host       | Description                                                                | Status |
|------------|----------------------------------------------------------------------------|--------|
| `openclaw` | Runs inside an existing [OpenClaw](https://github.com/openclaw/openclaw) gateway. | 🐣 (image + spawn profile; gateway integration Phase 5) |
| `hermes`   | Runs alongside a [Hermes Agent](https://hermes-agent.nousresearch.com/) gateway (Nous Research). | 🐣 (profile ready; dedicated image + integration TBD) |
| `pi`       | Bare Raspberry Pi with no gateway framework. Agent as a service.           | 🐣 (image + spawn profile; HTTP-only interface) |

See [`openclaw/`](./openclaw/), [`hermes/`](./hermes/), and [`pi/`](./pi/) for per-host details.

See [`openclaw/`](./openclaw/), [`hermes/`](./hermes/), and [`pi/`](./pi/) for per-host details.

Listing profiles from the CLI:

```bash
uv run nursery hosts
```

## Adapter Interface (sketch)

Each host adapter exposes:

```
host.register(agent)        # announce a newly spawned agent
host.route(msg, agent)      # deliver inbound message to agent
host.send(msg, channel)     # publish outbound reply
host.teardown(agent)        # clean up when agent is stopped
```

The shape is rough. See [`../docs/protocol.md`](../docs/protocol.md) for the ongoing discussion.

## Principles

- **Agents don't know what host they're on.** They speak a single protocol. The adapter translates.
- **Adapters are replaceable.** You can move an agent from OpenClaw to a bare Pi by swapping the adapter, not the agent.
- **Minimum privilege.** Adapters only expose what agents need. No raw host access.
