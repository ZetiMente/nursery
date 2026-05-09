# Agent ↔ Host Protocol

**Status: unresolved.** This is one of the most important design decisions in Nursery, and it's not yet made.

## The Question

How does a containerized agent receive inbound messages and publish outbound replies?

## Candidates

### 1. HTTP (agent-as-server)
Agent exposes an HTTP endpoint. Host POSTs inbound messages to it. Agent POSTs replies back to the host.

- ➕ Simple, debuggable, works anywhere
- ➕ Great tooling (curl, Postman, etc.)
- ➖ Per-agent port management
- ➖ Requires a routing layer on the host

### 2. Unix Socket per Agent
Each agent has a socket at `/var/run/nursery/<name>.sock` mounted into its container.

- ➕ No port conflicts
- ➕ Filesystem permissions = access control
- ➖ Socket requires careful cleanup on crash
- ➖ Harder to debug than HTTP

### 3. Message Bus (Redis / NATS)
Agents subscribe to their own channel on a shared bus; host publishes to it.

- ➕ Multi-host ready out of the box
- ➕ Built-in fan-out, pub/sub, replay
- ➖ Another service to run and secure
- ➖ Overkill for a single-Pi deployment

### 4. gRPC / bidirectional streaming
Typed, streaming, modern.

- ➕ Type safety
- ➕ Native streaming for long-running replies
- ➖ Tooling heavier than HTTP
- ➖ Harder for polyglot agents

## Leaning

For v0, probably **Unix sockets on a single host** + **HTTP option for remote hosts**. Start simple, migrate to a message bus if multi-host becomes important.

## Open Questions

- Streaming partial replies (LLMs produce tokens over time)
- Message ordering guarantees
- Backpressure when an agent is slow
- Authentication (is the socket enough? do agents need to prove identity?)
