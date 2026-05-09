# Security Policy

## Reporting a Vulnerability

**Please do not open public issues for security vulnerabilities.**

If you find a security issue, email the maintainer privately. We will acknowledge within a reasonable timeframe, investigate, and coordinate disclosure.

## Scope

Nursery is an agent-spawning framework. The highest-risk areas are:

- **Secrets handling** — leakage of OAuth tokens, API keys, credentials
- **Container escape** — an agent breaking out of its container onto the host
- **Cross-agent leakage** — one agent reading another agent's workspace or secrets
- **Supply chain** — compromise of the base image or dependencies

## Known Design Constraints

- Agents are assumed to be **mutually untrusted**. One agent should not be able to read another's state.
- The host gateway is trusted. Compromise of the gateway compromises all agents.
- Workspaces contain sensitive user data (memory, conversation history). Treat them like personal diaries.

## Not in Scope

- Issues in third-party model providers (Anthropic, OpenAI, Google, etc.)
- Issues in specific host runtimes (OpenClaw, Hermes) — report those upstream

## Responsible Disclosure

We ask that you give us a reasonable window to address issues before public disclosure. Standard industry practice (90 days) is fine.

Thank you for helping keep this project safe.
