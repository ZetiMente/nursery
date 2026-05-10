"""Agent lifecycle: spawn, ps, stop, rm, logs.

Thin wrapper over `docker run` that applies Nursery's mount, label, and
networking conventions consistently across OpenClaw / Hermes / Pi hosts.

Design:
- The Nursery CLI is the user-facing surface. It does NOT try to be a
  container runtime; it just tells Docker the right things.
- Every container Nursery manages is labeled `nursery.managed=true` plus
  `nursery.host=<host>` and `nursery.name=<agent-name>`. ps/stop/rm
  filter by these labels so we never touch someone else's containers.
- Workspace and secrets paths are resolved on the host before spawning.
  If a workspace dir doesn't exist, we create it. If a secrets dir
  doesn't exist, we create an empty one (a valid state).
- Soul path from the spec is copied into `<workspace>/.nursery/spec/`
  so the container has a stable `/spec/agent.yaml` + `/spec/soul.md`
  regardless of where the source files live on the host.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Host profiles
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HostProfile:
    """Baseline configuration for a host runtime.

    A HostProfile captures what Nursery should assume about an environment
    where an agent will run. Different hosts have different gateways,
    different Ollama conventions, different sensible defaults.

    Fields:
      name            Identifier used in specs (host: <name>) and --host.
      image_tag       Default image tag under the 'nursery/agent' repo.
      description     One-line human summary, printed by 'nursery hosts'.
      extra_run_args  Baseline docker-run args (networking, etc.).
      default_env     Extra env vars injected into every agent on this host.
                      Spec-level 'environment' still overrides these.
      publish_port    If set, -p <host_port>:7860 is added automatically.
                      None means network-only / gateway routes to the container.
      default_memory  Default --memory if the spec doesn't specify.
      default_cpus    Default --cpus if the spec doesn't specify.
      provisional     True for profiles whose design isn't finalized. A warning
                      is printed when the user spawns against a provisional host.
    """

    name: str
    image_tag: str
    description: str
    extra_run_args: tuple[str, ...] = ()
    default_env: tuple[tuple[str, str], ...] = ()
    publish_port: int | None = None
    default_memory: str | None = None
    default_cpus: float | None = None
    provisional: bool = False

    @property
    def image(self) -> str:
        return f"nursery/agent:{self.image_tag}"


HOST_PROFILES: dict[str, HostProfile] = {
    # ------------------------------------------------------------------
    # OpenClaw: agents run alongside an OpenClaw gateway on the same host.
    # The gateway is expected to be reachable at host.docker.internal:7770.
    # An Ollama daemon is typically also on the host.
    # ------------------------------------------------------------------
    "openclaw": HostProfile(
        name="openclaw",
        image_tag="openclaw",
        description="Agents alongside an OpenClaw gateway. Gateway + Ollama on host.",
        extra_run_args=(
            "--add-host=host.docker.internal:host-gateway",
        ),
        default_env=(
            ("NURSERY_HOST", "openclaw"),
            ("NURSERY_GATEWAY_URL", "http://host.docker.internal:7770"),
            ("NURSERY_OLLAMA_URL", "http://host.docker.internal:11434"),
        ),
        # OpenClaw gateway routes; no need to publish the agent's port.
        publish_port=None,
        default_memory=None,
        default_cpus=None,
        provisional=False,
    ),

    # ------------------------------------------------------------------
    # Hermes: Nous Research's agent framework. Direct sibling of OpenClaw —
    # persistent memory, skills, messaging gateway (Telegram, Discord, Slack,
    # WhatsApp, Signal, and more). API server defaults to localhost:8642.
    # Agents here live alongside a `hermes gateway` process on the host.
    # ------------------------------------------------------------------
    "hermes": HostProfile(
        name="hermes",
        image_tag="base",  # No dedicated image yet; inherits base. Own Dockerfile later.
        description="Agents alongside a Hermes (Nous Research) gateway on the host.",
        extra_run_args=(
            "--add-host=host.docker.internal:host-gateway",
        ),
        default_env=(
            ("NURSERY_HOST", "hermes"),
            ("NURSERY_GATEWAY_URL", "http://host.docker.internal:8642"),
            ("NURSERY_OLLAMA_URL", "http://host.docker.internal:11434"),
        ),
        publish_port=None,
        default_memory=None,
        default_cpus=None,
        provisional=False,
    ),

    # ------------------------------------------------------------------
    # Pi (bare): no gateway. The agent is the service. Published on the
    # host on port 7860 by default so you can curl it directly. Resources
    # capped conservatively.
    # ------------------------------------------------------------------
    "pi": HostProfile(
        name="pi",
        image_tag="base",
        description="Bare Pi / edge. No gateway. Agent HTTP published to host.",
        extra_run_args=(
            "--add-host=host.docker.internal:host-gateway",
        ),
        default_env=(
            ("NURSERY_HOST", "pi"),
            ("NURSERY_OLLAMA_URL", "http://host.docker.internal:11434"),
        ),
        publish_port=7860,
        default_memory="6g",
        default_cpus=4.0,
        provisional=False,
    ),
}


# ---------------------------------------------------------------------------
# Spec loading / resolution
# ---------------------------------------------------------------------------


def _load_spec(spec_path: Path) -> dict:
    """Delegate to the validate command's loader/validator for consistency."""
    from nursery_cli._cli import _load_yaml, _load_schema, _validate

    if not spec_path.exists():
        sys.stderr.write(f"error: spec file not found: {spec_path}\n")
        raise SystemExit(2)

    spec = _load_yaml(spec_path)
    if not isinstance(spec, dict):
        sys.stderr.write("error: spec must be a mapping\n")
        raise SystemExit(2)

    errors = _validate(spec, _load_schema())
    if errors:
        sys.stderr.write(f"error: spec is invalid ({len(errors)} issue(s)):\n")
        for e in errors:
            sys.stderr.write(e + "\n")
        raise SystemExit(1)

    return spec


def _expand(p: str) -> Path:
    """Expand ~ and env vars in a path."""
    return Path(os.path.expandvars(os.path.expanduser(p))).resolve()


def _ensure_dir(path: Path, what: str) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        sys.stderr.write(f"error: cannot create {what} at {path}: {e}\n")
        raise SystemExit(2) from None


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _docker(args: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = ["docker", *args]
    try:
        return subprocess.run(
            cmd,
            check=check,
            text=True,
            capture_output=capture,
        )
    except FileNotFoundError:
        sys.stderr.write(
            "error: 'docker' not found on PATH.\n"
            "       Install Docker (https://docs.docker.com/engine/install/) and retry.\n"
        )
        raise SystemExit(127) from None
    except subprocess.CalledProcessError as e:
        if capture:
            sys.stderr.write(e.stderr or "")
        raise


def _resolve_docker_prefix() -> list[str]:
    """Return the docker invocation prefix.

    If the user can run 'docker version' without sudo, we use docker directly.
    Otherwise fall back to sudo. A human-readable warning is printed once.
    """
    try:
        subprocess.run(
            ["docker", "version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return ["docker"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        if shutil.which("sudo") is None:
            sys.stderr.write(
                "error: docker is not usable without sudo, and sudo is not installed.\n"
                "       Add your user to the 'docker' group (then log out + in).\n"
            )
            raise SystemExit(126) from None
        sys.stderr.write(
            "note: using 'sudo docker' (current user not in docker group).\n"
        )
        return ["sudo", "docker"]


# ---------------------------------------------------------------------------
# Spawn
# ---------------------------------------------------------------------------


def _build_run_args(
    spec: dict,
    host: HostProfile,
    workspace: Path,
    secrets_dir: Path,
    staged_spec_dir: Path,
    *,
    name: str,
    image: str,
    detach: bool,
    publish_port: int | None,
) -> list[str]:
    args: list[str] = [
        "run",
        "--name", name,
        "--label", "nursery.managed=true",
        "--label", f"nursery.host={host.name}",
        "--label", f"nursery.name={spec['name']}",
        "--restart", "unless-stopped",
        # Conventions
        "-v", f"{staged_spec_dir}:/spec:ro",
        "-v", f"{workspace}:/workspace",
        "-v", f"{secrets_dir}:/run/secrets:ro",
        # Core runtime conventions
        "-e", "NURSERY_SPEC_PATH=/spec/agent.yaml",
        "-e", "NURSERY_WORKSPACE=/workspace",
        "-e", "NURSERY_SECRETS_DIR=/run/secrets",
    ]

    # Host profile env first (spec-level 'environment' below can override).
    spec_env = {k: str(v) for k, v in (spec.get("environment") or {}).items()}
    for k, v in host.default_env:
        if k not in spec_env:
            args += ["-e", f"{k}={v}"]

    # Spec-level environment
    for k, v in spec_env.items():
        args += ["-e", f"{k}={v}"]

    # Resources — spec wins, then host profile defaults, then Docker defaults.
    resources = spec.get("resources") or {}
    memory = resources.get("memory", host.default_memory)
    cpus = resources.get("cpus", host.default_cpus)
    if memory:
        args += ["--memory", str(memory)]
    if cpus is not None:
        args += ["--cpus", str(cpus)]

    # Port publishing
    if publish_port is not None:
        args += ["-p", f"{publish_port}:7860"]

    # Host-specific baseline (--add-host, etc.)
    args += list(host.extra_run_args)

    if detach:
        args += ["-d"]

    args.append(image)
    return args


def _stage_spec(spec_path: Path, workspace: Path, spec: dict) -> Path:
    """Copy the spec (and soul) into a stable mount directory under the workspace.

    We do this so the container always mounts `/spec/agent.yaml` regardless of
    where the original files live on the host filesystem.
    """
    stage = workspace / ".nursery" / "spec"
    stage.mkdir(parents=True, exist_ok=True)

    # Copy spec, rewriting the soul reference to a stable in-stage path.
    soul_ref = spec.get("soul")
    spec_out = dict(spec)

    if soul_ref:
        source_soul = Path(soul_ref)
        if not source_soul.is_absolute():
            source_soul = (spec_path.parent / soul_ref).resolve()
        if source_soul.exists():
            shutil.copy2(source_soul, stage / "soul.md")
            spec_out["soul"] = "./soul.md"
        else:
            sys.stderr.write(
                f"warn: soul file not found at {source_soul}; container will boot without a soul\n"
            )
            spec_out.pop("soul", None)

    import yaml  # type: ignore

    (stage / "agent.yaml").write_text(
        yaml.safe_dump(spec_out, sort_keys=False),
        encoding="utf-8",
    )
    return stage


def cmd_spawn(args: argparse.Namespace) -> int:
    if not _docker_available():
        sys.stderr.write("error: docker not found on PATH.\n")
        return 127

    spec_path = Path(args.spec).resolve()
    spec = _load_spec(spec_path)

    host_name = args.host or spec.get("host", "pi")
    if host_name not in HOST_PROFILES:
        sys.stderr.write(f"error: unknown host {host_name!r} (expected one of {sorted(HOST_PROFILES)})\n")
        return 2
    host = HOST_PROFILES[host_name]
    image = args.image or host.image

    if host.provisional:
        sys.stderr.write(
            f"note: host profile '{host.name}' is PROVISIONAL — defaults may change.\n"
            f"      {host.description}\n"
        )

    workspace = _expand(spec["workspace"])
    _ensure_dir(workspace, "workspace")

    secrets_dir = _expand(args.secrets_dir) if args.secrets_dir else (workspace / ".nursery" / "secrets")
    _ensure_dir(secrets_dir, "secrets directory")

    staged_spec_dir = _stage_spec(spec_path, workspace, spec)

    container_name = args.name or f"nursery-{spec['name']}"

    # Publish port: CLI flag > profile default > none.
    if args.publish_port is not None:
        publish_port: int | None = args.publish_port
    elif args.no_publish:
        publish_port = None
    else:
        publish_port = host.publish_port

    # --- Pre-spawn preflight (on by default; --no-preflight to skip) ---
    if not args.dry_run and not args.no_preflight:
        from nursery_cli import preflight
        print("==> preflight...")
        report = preflight.run_preflight_for_spawn(spec, workspace)
        print(report.render(use_color=sys.stdout.isatty()))
        if report.has_failures():
            sys.stderr.write(
                "\nerror: preflight failed. Fix the issues above, or run with --no-preflight to skip.\n"
                "       Run `nursery doctor` for a full host readiness report.\n"
            )
            return 1
        print()

    run_args = _build_run_args(
        spec,
        host,
        workspace,
        secrets_dir,
        staged_spec_dir,
        name=container_name,
        image=image,
        detach=not args.foreground,
        publish_port=publish_port,
    )

    docker_prefix = ["docker"] if args.dry_run else _resolve_docker_prefix()
    full_cmd = [*docker_prefix, *run_args]

    if args.dry_run:
        print("# would run:")
        print(" \\\n  ".join(full_cmd))
        print()
        print(f"# host profile: {host.name} ({host.description})")
        print(f"# workspace: {workspace}")
        print(f"# secrets:   {secrets_dir}")
        print(f"# staged spec: {staged_spec_dir}")
        if publish_port:
            print(f"# published: http://localhost:{publish_port}")
        return 0

    print(f"==> spawning '{spec['name']}' on host '{host.name}' (image {image})")
    print(f"    workspace: {workspace}")
    print(f"    container: {container_name}")
    if publish_port:
        print(f"    published: http://localhost:{publish_port}")
    try:
        result = subprocess.run(full_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        sys.stderr.write("error: docker run failed\n")
        sys.stderr.write(e.stderr or "")
        return e.returncode

    cid = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
    print(f"    container id: {cid or '(unknown)'}")

    # --- Post-spawn verification (on by default; --no-wait to skip) ---
    if not args.no_wait and publish_port:
        from nursery_cli import preflight
        print(f"==> verifying container health (up to {args.wait_timeout}s)...")
        verify = preflight.run_post_spawn_verify(
            agent_url=f"http://localhost:{publish_port}",
            timeout_s=args.wait_timeout,
        )
        print(verify.render(use_color=sys.stdout.isatty()))
        if verify.has_failures():
            sys.stderr.write(
                f"\nwarning: container is running but not healthy. Inspect:\n"
                f"  nursery logs {spec['name']}\n"
                f"  nursery doctor\n"
            )
            # Don't return failure: container is up; user can inspect.

    print(f"    logs:    nursery logs {spec['name']}")
    print(f"    stop:    nursery stop {spec['name']}")
    return 0


# ---------------------------------------------------------------------------
# ps / stop / rm / logs
# ---------------------------------------------------------------------------


def _find_container(name: str, *, include_stopped: bool = True) -> str | None:
    """Find a Nursery-managed container by agent name. Returns container ID or None."""
    docker = _resolve_docker_prefix()
    filters = [
        "-f", "label=nursery.managed=true",
        "-f", f"label=nursery.name={name}",
    ]
    cmd = [*docker, "ps"]
    if include_stopped:
        cmd.append("-a")
    cmd += [*filters, "--format", "{{.ID}}"]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    ids = result.stdout.strip().splitlines()
    return ids[0] if ids else None


def cmd_ps(args: argparse.Namespace) -> int:
    docker = _resolve_docker_prefix()
    cmd: list[str] = [*docker, "ps"]
    if args.all:
        cmd.append("-a")
    cmd += [
        "-f", "label=nursery.managed=true",
        "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Labels}}",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    lines = result.stdout.strip().splitlines()
    if not lines:
        print("(no nursery-managed containers)")
        return 0
    # Print a friendly table
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 4:
            print(line)
            continue
        name, status, image, labels = parts[0], parts[1], parts[2], parts[3]
        # Extract nursery.name and nursery.host from the labels blob
        label_map = dict(kv.split("=", 1) for kv in labels.split(",") if "=" in kv)
        agent = label_map.get("nursery.name", "?")
        host = label_map.get("nursery.host", "?")
        print(f"{agent:<24} {host:<10} {status:<30} {image}")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    cid = _find_container(args.name, include_stopped=False)
    if not cid:
        sys.stderr.write(f"error: no running container for agent {args.name!r}\n")
        return 1
    docker = _resolve_docker_prefix()
    subprocess.run([*docker, "stop", cid], check=True, capture_output=True, text=True)
    print(f"stopped {args.name} (workspace preserved)")
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    cid = _find_container(args.name, include_stopped=True)
    if not cid:
        sys.stderr.write(f"error: no container for agent {args.name!r}\n")
        return 1
    docker = _resolve_docker_prefix()
    subprocess.run([*docker, "rm", "-f", cid], check=True, capture_output=True, text=True)
    print(f"removed container {args.name}")
    if args.purge:
        sys.stderr.write("note: --purge not implemented yet; workspace kept.\n")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    cid = _find_container(args.name, include_stopped=True)
    if not cid:
        sys.stderr.write(f"error: no container for agent {args.name!r}\n")
        return 1
    docker = _resolve_docker_prefix()
    cmd = [*docker, "logs"]
    if args.follow:
        cmd.append("-f")
    if args.tail is not None:
        cmd += ["--tail", str(args.tail)]
    cmd.append(cid)
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        pass
    return 0


# ---------------------------------------------------------------------------
# argparse wiring — invoked by the top-level CLI
# ---------------------------------------------------------------------------


def cmd_hosts(args: argparse.Namespace) -> int:
    """List available host profiles."""
    print(f"{'NAME':<10} {'IMAGE':<28} {'PORT':<6} {'STATUS':<14} DESCRIPTION")
    for name in sorted(HOST_PROFILES):
        h = HOST_PROFILES[name]
        status = "provisional" if h.provisional else "ready"
        port = str(h.publish_port) if h.publish_port else "-"
        print(f"{h.name:<10} {h.image:<28} {port:<6} {status:<14} {h.description}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Run a standalone host readiness report."""
    from nursery_cli import preflight
    print("nursery doctor — host readiness report")
    print()
    report = preflight.run_doctor()
    print(report.render(use_color=sys.stdout.isatty()))
    print()
    if report.has_failures():
        print("Result: issues found. Fix the items marked ✗ and re-run `nursery doctor`.")
        return 1
    print("Result: host looks ready for `nursery spawn`.")
    return 0


def register_subparsers(subparsers) -> None:  # type: ignore[no-untyped-def]
    sp_spawn = subparsers.add_parser("spawn", help="Spawn an agent container from a spec.")
    sp_spawn.add_argument("spec", help="Path to an agent spec (.yaml, .yml, or .json).")
    sp_spawn.add_argument("--host", choices=sorted(HOST_PROFILES), help="Override host from spec.")
    sp_spawn.add_argument("--image", help="Override image (defaults from host profile).")
    sp_spawn.add_argument("--name", help="Override container name (default nursery-<agent-name>).")
    sp_spawn.add_argument("--secrets-dir", help="Override secrets directory (default workspace/.nursery/secrets).")
    sp_spawn.add_argument("--publish-port", type=int, help="Publish agent HTTP on host port (overrides host profile default).")
    sp_spawn.add_argument("--no-publish", action="store_true", help="Do not publish the agent's port to the host.")
    sp_spawn.add_argument("--foreground", action="store_true", help="Run attached instead of detached.")
    sp_spawn.add_argument("--dry-run", action="store_true", help="Print the docker command instead of running it.")
    sp_spawn.add_argument("--no-preflight", action="store_true", help="Skip pre-spawn host readiness checks.")
    sp_spawn.add_argument("--no-wait", action="store_true", help="Don't wait for the container to report healthy.")
    sp_spawn.add_argument("--wait-timeout", type=float, default=30.0, help="Seconds to wait for /healthz (default 30).")
    sp_spawn.set_defaults(func=cmd_spawn)

    sp_ps = subparsers.add_parser("ps", help="List Nursery-managed containers.")
    sp_ps.add_argument("-a", "--all", action="store_true", help="Include stopped containers.")
    sp_ps.set_defaults(func=cmd_ps)

    sp_stop = subparsers.add_parser("stop", help="Stop an agent (workspace persists).")
    sp_stop.add_argument("name", help="Agent name (from spec).")
    sp_stop.set_defaults(func=cmd_stop)

    sp_rm = subparsers.add_parser("rm", help="Remove an agent container.")
    sp_rm.add_argument("name", help="Agent name (from spec).")
    sp_rm.add_argument("--purge", action="store_true", help="(future) also delete workspace.")
    sp_rm.set_defaults(func=cmd_rm)

    sp_logs = subparsers.add_parser("logs", help="Tail container logs.")
    sp_logs.add_argument("name", help="Agent name (from spec).")
    sp_logs.add_argument("-f", "--follow", action="store_true", help="Follow output.")
    sp_logs.add_argument("-n", "--tail", type=int, help="Show only last N lines.")
    sp_logs.set_defaults(func=cmd_logs)

    sp_hosts = subparsers.add_parser("hosts", help="List available host profiles.")
    sp_hosts.set_defaults(func=cmd_hosts)

    sp_doctor = subparsers.add_parser(
        "doctor",
        help="Check host readiness (docker, ollama binding, firewall, etc.)",
    )
    sp_doctor.set_defaults(func=cmd_doctor)
