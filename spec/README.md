# Agent Spec

This directory defines the **declarative schema** for an agent.

An agent spec is a YAML (or JSON) file describing everything needed to spawn an agent:

- Identity (name, persona/soul file)
- Runtime (image, model, resources)
- Integrations (channels, capabilities)
- State (workspace mount, secrets)

## Design Principles

1. **Declarative, not imperative.** The spec describes what the agent *is*, not how to build it.
2. **Portable.** The same spec should work on OpenClaw, Hermes, or a bare Pi (with the right host adapter).
3. **Human-readable.** YAML over JSON. Comments allowed. Defaults sensible.
4. **Validatable.** A JSON Schema lives in this directory so specs can be linted before `spawn`.

## Status

Schema draft lives in [`agent.schema.json`](./agent.schema.json) *(to be written)*.

Example specs live in [`../examples/agents/`](../examples/agents/).
