# CLI

The `nursery` command-line interface.

## Current Commands (Phase 1)

```bash
nursery validate <spec.yaml>   # Lint a spec against the schema
nursery --version              # Show version
nursery --help                 # Show help
```

## Planned Commands (future phases)

```bash
nursery spawn <spec.yaml>      # Phase 2: create and start an agent
nursery stop <name>            # Phase 2
nursery start <name>           # Phase 2
nursery rm <name>              # Phase 2
nursery ps                     # Phase 2
nursery ls                     # Phase 2
nursery logs <name>            # Phase 2
nursery fork <spec> --as <name>  # Phase 7
nursery inspect <name>         # Phase 2
nursery exec <name> <cmd>      # Phase 2
```

## Install / Run (dev)

No install step yet. Run directly from the repo:

```bash
# From repo root:
./cli/nursery validate examples/agents/example.yaml
```

Requires Python 3.10+ with `pyyaml` and `jsonschema`:

```bash
pip install pyyaml jsonschema
```

## Design Notes

- Thin wrapper over Docker + host adapter hooks (once Phase 2+ lands).
- State lives on the host filesystem, not in the CLI itself. Reinstalling the CLI should not lose any agents.
- Should work identically on a laptop, a server, or a Pi.

## Status

🐣 Phase 1 complete: `validate` works. Spawn / lifecycle commands come in Phase 2.
