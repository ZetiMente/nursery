# CLI

The `nursery` command-line interface.

## Commands

```bash
nursery validate <spec.yaml>           # Lint a spec against the schema
nursery spawn <spec.yaml> [--dry-run]  # Start a container from the spec
nursery ps [-a]                        # List Nursery-managed containers
nursery stop <agent-name>              # Stop a running agent (workspace persists)
nursery rm <agent-name>                # Remove a container (workspace persists)
nursery logs <agent-name> [-f] [-n N]  # Tail container logs
nursery --version
nursery --help
```

## Planned (not yet implemented)

```bash
nursery start <agent-name>             # Start a previously-stopped agent
nursery exec <agent-name> <cmd>        # Run a command inside the container
nursery inspect <agent-name>           # Show agent state (workspace, secrets, channels)
nursery fork <spec> --as <name>        # Clone blueprint into a new individual (Phase 7)
```

## Run (dev, via uv)

From the repo root:

```bash
uv sync                                # install deps + editable package
uv run nursery spawn examples/agents/gemma4-layla.yaml
```

Or install as a tool (no repo required):

```bash
uv tool install .                                        # from a clone
uv tool install git+https://github.com/ZetiMente/nursery  # direct from GitHub
nursery spawn path/to/agent.yaml
```

Python 3.10+ required. Dependencies (`pyyaml`, `jsonschema`) install automatically.

## Host profiles

`spawn` reads the spec's `host` field (`openclaw` | `hermes` | `pi`) to pick the default image tag and baseline docker args. Override with `--host <name>`.

| Host      | Default image               | Extra docker args                                    |
|-----------|-----------------------------|------------------------------------------------------|
| openclaw  | `nursery/agent:openclaw`    | `--add-host=host.docker.internal:host-gateway`       |
| hermes    | `nursery/agent:base`        | `--add-host=host.docker.internal:host-gateway`       |
| pi        | `nursery/agent:base`        | `--add-host=host.docker.internal:host-gateway`       |

## Conventions

Every Nursery-managed container gets these labels so lifecycle commands can find them safely:

```
nursery.managed=true
nursery.host=<openclaw|hermes|pi>
nursery.name=<agent-name-from-spec>
```

The container is named `nursery-<agent-name>` by default (override with `--name`).

On first spawn, the CLI creates under the workspace:

```
<workspace>/
├── .nursery/
│   ├── spec/
│   │   ├── agent.yaml         # Staged copy with normalized paths
│   │   └── soul.md            # Copied from spec['soul'] for stable mount
│   └── secrets/               # Empty by default; populated per-agent by operator
└── (workspace content the agent writes over time)
```

This keeps the container's view (`/spec/agent.yaml`, `/spec/soul.md`, `/run/secrets/*`, `/workspace`) uniform across hosts, regardless of where the original files live on the host filesystem.

## Sudo note

If the current user is not in the `docker` group, the CLI falls back to `sudo docker` and prints a one-line notice on stderr. To drop that, add your user:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
```

## Status

🐥 Phase 2 essentials complete. `validate`, `spawn`, `ps`, `stop`, `rm`, `logs` all working.
`start`, `exec`, `inspect` come when actually needed.
