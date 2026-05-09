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
nursery hosts                          # List available host profiles
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

`spawn` reads the spec's `host` field (`openclaw` | `hermes` | `pi`) to pick the default image tag, environment, and port-publishing behavior. Override with `--host <name>`.

Run `nursery hosts` for a live listing.

| Host      | Image                     | Default env                                    | Port publish | Status       |
|-----------|---------------------------|------------------------------------------------|--------------|--------------|
| openclaw  | `nursery/agent:openclaw`  | `NURSERY_GATEWAY_URL=http://host:7770`         | (none, gateway routes) | ready |
| hermes    | `nursery/agent:base`      | `NURSERY_GATEWAY_URL=http://host:7771`         | (none) | **provisional** |
| pi        | `nursery/agent:base`      | `NURSERY_OLLAMA_URL=http://host:11434`         | `7860:7860`  | ready |

All three inject `NURSERY_HOST=<profile-name>` and add `--add-host=host.docker.internal:host-gateway` so the container can reach host services on Linux.

Spec-level `environment:` entries override profile defaults. Spec-level `resources:` overrides profile memory/cpu defaults.

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
