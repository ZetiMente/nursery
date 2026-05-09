# Agent Spec

This directory defines the **declarative schema** for a Nursery agent.

An agent spec is a YAML (or JSON) file describing everything needed to spawn an agent:

- **Identity** — name, persona/soul file
- **Runtime** — image, model, resources
- **Integrations** — channels, capabilities
- **State** — workspace mount, secrets (by name, never by value)

## Design Principles

1. **Declarative, not imperative.** The spec describes what the agent *is*, not how to build it.
2. **Portable.** The same spec should work on OpenClaw, Hermes, or a bare Pi.
3. **Human-readable.** YAML over JSON. Comments allowed. Defaults sensible.
4. **Validatable.** A JSON Schema lives here so specs can be linted before `spawn`.
5. **Secrets-safe.** Secrets are referenced by name only. Values never appear in a spec.

## Schema

[`agent.schema.json`](./agent.schema.json) — Draft 2020-12 JSON Schema.

Key rules:

- `name`, `image`, `model`, `workspace` are **required**.
- `name` must be kebab-case (`^[a-z][a-z0-9-]{1,62}$`) for safe use as a container name.
- `model` is `<provider>/<model>` (e.g. `anthropic/claude-opus`, `google/gemini-pro`, `local/llama-3`).
- `additionalProperties: false` — typos in field names are caught immediately.
- `secrets` contains **names only**. The host resolves them to mounted files. Never put a value in the spec.

## Validating

```bash
# From repo root:
./cli/nursery validate examples/agents/example.yaml
```

Exit codes:
- `0` — valid
- `1` — invalid (errors printed)
- `2` — could not read/parse file, missing deps, etc.

## Example

See [`../examples/agents/example.yaml`](../examples/agents/example.yaml) for a fully-populated spec that passes validation.

## Status

🐥 Schema working. Fields will likely grow as phases progress; the schema will version if breaking changes become necessary.
