# CLI

The `nursery` command-line interface.

## Commands

```bash
nursery validate <spec.yaml>           # Lint a spec against the schema
nursery spawn <spec.yaml> [--dry-run]  # Start a container from the spec (preflight on by default)
nursery doctor                         # Standalone host readiness report
nursery ps [-a]                        # List Nursery-managed containers
nursery stop <agent-name>              # Stop a running agent (workspace persists)
nursery rm <agent-name>                # Remove a container (workspace persists)
nursery logs <agent-name> [-f] [-n N]  # Tail container logs
nursery hosts                          # List available host profiles
nursery --version
nursery --help
```

## Preflight

`nursery spawn` runs pre-spawn host checks by default. If any fail, the container is NOT created and the CLI prints the exact fix command for each issue:

```
==> preflight...
  ✓ docker  v29.4.3
  ✓ workspace  writable (/home/matthew/nursery/agents/layla-pi/workspace)
  ✓ ollama (host)  v0.23.2 at http://127.0.0.1:11434
  ✗ ollama binding  bound to 127.0.0.1 only — containers can't reach it
      fix:
        sudo mkdir -p /etc/systemd/system/ollama.service.d
        echo '[Service]
        Environment="OLLAMA_HOST=0.0.0.0"' | \
          sudo tee /etc/systemd/system/ollama.service.d/override.conf
        sudo systemctl daemon-reload && sudo systemctl restart ollama
  ✗ bridge → ollama  container cannot reach host Ollama
      fix:
        sudo ufw allow from 172.17.0.0/16 to any port 11434 proto tcp
        sudo ufw reload
  ✓ model batiai/gemma4-e2b:q4  pulled

error: preflight failed. Fix the issues above, or run with --no-preflight to skip.
       Run `nursery doctor` for a full host readiness report.
```

After a successful `docker run`, spawn also polls `/healthz` until `backend_ok=true` or `--wait-timeout` expires. Use `--no-wait` to skip.

`nursery doctor` runs the same checks standalone, no spec required — good for onboarding a new host.

Flags:

- `--no-preflight` — skip pre-spawn checks.
- `--no-wait` — don't wait for container health.
- `--wait-timeout N` — seconds to wait for `/healthz` (default 30).

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

| Host       | Image                     | Default env                                    | Port publish | Status       |
|------------|---------------------------|------------------------------------------------|--------------|--------------|
| openclaw   | `nursery/agent:openclaw`  | `NURSERY_GATEWAY_URL=http://host:7770`         | (none, gateway routes) | ready |
| hermes     | `nursery/agent:base`      | `NURSERY_GATEWAY_URL=http://host:8642`         | (none, gateway routes) | ready |
| pi         | `nursery/agent:base`      | `NURSERY_HOST=pi`                              | (none) | **provisional** |
| standalone | `nursery/agent:base`      | `NURSERY_OLLAMA_URL=http://host:11434`         | `7860:7860`  | ready |

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
