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

## Run (dev, via uv)

From the repo root:

```bash
uv sync                # install deps + editable package
uv run nursery validate examples/agents/example.yaml
```

Or install as a tool (no repo required):

```bash
uv tool install .                               # from a clone
uv tool install git+https://github.com/ZetiMente/nursery  # direct from GitHub
nursery validate path/to/agent.yaml
```

Python 3.10+ required. Dependencies (`pyyaml`, `jsonschema`) install automatically.

## Layout

```
cli/
└── src/
    └── nursery_cli/
        ├── __init__.py
        └── _cli.py        # argparse + commands live here
```

Build config (`pyproject.toml`) lives at the repo root.

## Design Notes

- Thin wrapper over Docker + host adapter hooks (once Phase 2+ lands).
- State lives on the host filesystem, not in the CLI itself. Reinstalling should not lose agents.
- Should work identically on a laptop, a server, or a Pi.
- Single `pyproject.toml` at the repo root; the schema in `spec/` is force-included into the wheel so installed users don't need the repo.

## Status

🐥 Phase 1 complete: `validate` works, package installs cleanly via `uv`.
Spawn / lifecycle commands come in Phase 2.
