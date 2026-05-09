# CLI

The `nursery` command-line interface.

## Planned Commands

```bash
nursery spawn <spec.yaml>      # Create and start an agent
nursery stop <name>            # Stop a running agent (workspace persists)
nursery start <name>           # Start a previously-stopped agent
nursery rm <name>              # Delete an agent (destroys workspace — requires --force)
nursery ps                     # List running agents
nursery ls                     # List all known agents (running or stopped)
nursery fork <spec.yaml> --as <name>  # Clone blueprint into a new individual
nursery logs <name>            # Tail agent logs
nursery exec <name> <cmd>      # Run a command inside an agent's container
nursery inspect <name>         # Show agent state (workspace path, secrets, channels)
nursery validate <spec.yaml>   # Lint a spec against the schema
```

## Design Notes

- Thin wrapper over Docker + host adapter hooks.
- State lives on the host filesystem, not in the CLI itself. Reinstalling the CLI should not lose any agents.
- Should work identically on a laptop, a server, or a Pi.

## Status

Not implemented. Language TBD (leaning Python for portability; Go is tempting for single-binary distribution).
