# OpenClaw Host Adapter

Runs Nursery agents as containers alongside an existing OpenClaw gateway.

## Responsibilities

- Register agents with the OpenClaw gateway when they spawn
- Route inbound channel messages (Telegram, Discord, Signal, etc.) to the right agent container
- Publish outbound replies back through OpenClaw's channel infrastructure
- Handle OpenClaw-specific conventions (workspaces, session isolation, subagents)

## Status

🥚 Not implemented. This is where we'll wire agents into the existing `~/.openclaw/` ecosystem.
