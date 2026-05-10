"""Preflight checks — diagnose host readiness before (and after) `nursery spawn`.

Philosophy: a turnkey system isn't just one that works when everything's
right — it's one that tells you exactly what's wrong when something isn't.

This module is used by:
  - `nursery doctor`  : standalone host readiness report (no spawn needed)
  - `nursery spawn`   : pre-spawn check to fail fast with actionable errors,
                        and post-spawn verification that the container is
                        actually healthy.

Each check produces a Result with: name, status, message, and optionally a
concrete fix command the user can copy-paste.

Checks are DIAGNOSTIC. We do not mutate the host automatically (that would
be surprising and destructive). We explain, suggest, and let the user act.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Status(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


# ANSI colors — keep simple; no external dep.
_COLOR = {
    Status.OK:   "\033[32m",   # green
    Status.WARN: "\033[33m",   # yellow
    Status.FAIL: "\033[31m",   # red
    Status.SKIP: "\033[90m",   # gray
}
_RESET = "\033[0m"
_GLYPH = {
    Status.OK: "✓",
    Status.WARN: "⚠",
    Status.FAIL: "✗",
    Status.SKIP: "·",
}


@dataclass
class Result:
    name: str
    status: Status
    message: str = ""
    fix: str | None = None        # copy-pasteable command the user can run
    detail: str | None = None     # extra multi-line info, optional


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, r: Result) -> None:
        self.results.append(r)

    @property
    def worst(self) -> Status:
        order = [Status.OK, Status.SKIP, Status.WARN, Status.FAIL]
        w = Status.OK
        for r in self.results:
            if order.index(r.status) > order.index(w):
                w = r.status
        return w

    def has_failures(self) -> bool:
        return any(r.status == Status.FAIL for r in self.results)

    def render(self, use_color: bool = True) -> str:
        lines: list[str] = []
        for r in self.results:
            color = _COLOR[r.status] if use_color else ""
            reset = _RESET if use_color else ""
            glyph = _GLYPH[r.status]
            lines.append(f"  {color}{glyph} {r.name}{reset}  {r.message}")
            if r.detail:
                for dline in r.detail.splitlines():
                    lines.append(f"      {dline}")
            if r.fix and r.status in (Status.FAIL, Status.WARN):
                lines.append("      fix:")
                for fline in r.fix.splitlines():
                    lines.append(f"        {fline}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr). Never raises."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return 255, "", str(e)


def _docker_cmd_prefix() -> list[str] | None:
    """Return the docker prefix if docker is usable, else None."""
    if shutil.which("docker") is None:
        return None
    rc, _, _ = _run(["docker", "version"], timeout=5)
    if rc == 0:
        return ["docker"]
    if shutil.which("sudo"):
        rc, _, _ = _run(["sudo", "-n", "docker", "version"], timeout=5)
        if rc == 0:
            return ["sudo", "docker"]
    return None  # docker is installed but not reachable


def check_docker() -> Result:
    if shutil.which("docker") is None:
        return Result(
            name="docker",
            status=Status.FAIL,
            message="not installed",
            fix="Install Docker: https://docs.docker.com/engine/install/",
        )
    prefix = _docker_cmd_prefix()
    if prefix is None:
        return Result(
            name="docker",
            status=Status.FAIL,
            message="daemon not reachable",
            fix=(
                "Start the daemon and make sure your user can reach it:\n"
                "  sudo systemctl start docker\n"
                "  sudo usermod -aG docker \"$USER\"   # then log out + in"
            ),
        )
    rc, out, _ = _run([*prefix, "version", "--format", "{{.Server.Version}}"], timeout=5)
    version = out.strip() or "unknown"
    if prefix[0] == "sudo":
        return Result(
            name="docker",
            status=Status.WARN,
            message=f"v{version} reachable via sudo (not in docker group)",
            fix="sudo usermod -aG docker \"$USER\"  # then log out + in",
        )
    return Result(name="docker", status=Status.OK, message=f"v{version}")


def check_host_gateway_resolution() -> Result:
    """Verify host.docker.internal resolves from a throwaway container."""
    prefix = _docker_cmd_prefix()
    if prefix is None:
        return Result(
            name="host.docker.internal",
            status=Status.SKIP,
            message="docker not available",
        )

    cmd = [
        *prefix, "run", "--rm",
        "--add-host=host.docker.internal:host-gateway",
        "--entrypoint=getent",
        "alpine",
        "hosts", "host.docker.internal",
    ]
    rc, out, err = _run(cmd, timeout=30)
    if rc != 0:
        return Result(
            name="host.docker.internal",
            status=Status.FAIL,
            message="cannot resolve from docker bridge",
            detail=(err or out).strip() or None,
            fix=(
                "This is usually a Docker version mismatch. Update to a recent Docker (>= 20.10)\n"
                "and ensure --add-host=host.docker.internal:host-gateway is supported."
            ),
        )
    ip = (out.split() or [""])[0]
    return Result(
        name="host.docker.internal",
        status=Status.OK,
        message=f"resolves to {ip}",
    )


def check_ollama_local(url: str) -> Result:
    """Is Ollama responding on the host at the expected URL?"""
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/version", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
        return Result(
            name="ollama (host)",
            status=Status.OK,
            message=f"v{data.get('version','?')} at {url}",
        )
    except urllib.error.URLError as e:
        return Result(
            name="ollama (host)",
            status=Status.FAIL,
            message=f"not reachable from host at {url}",
            detail=str(e),
            fix=(
                "Install + start Ollama:\n"
                "  curl -fsSL https://ollama.com/install.sh | sh\n"
                "  sudo systemctl start ollama"
            ),
        )


def check_ollama_binding() -> Result:
    """Confirm Ollama is bound to an interface reachable from the docker bridge.

    The default install binds to 127.0.0.1 only, which containers cannot reach.
    We check `ss -lnt` if available; otherwise we fall through with a SKIP.
    """
    if shutil.which("ss") is None:
        return Result(
            name="ollama binding",
            status=Status.SKIP,
            message="ss not installed; cannot inspect listening interface",
        )
    rc, out, _ = _run(["ss", "-lnt"], timeout=5)
    if rc != 0:
        return Result(
            name="ollama binding",
            status=Status.SKIP,
            message="ss failed; cannot inspect",
        )
    listening_lines = [
        line for line in out.splitlines() if ":11434" in line and "LISTEN" in line
    ]
    if not listening_lines:
        return Result(
            name="ollama binding",
            status=Status.FAIL,
            message="not listening on :11434",
            fix=(
                "Start Ollama (systemctl start ollama) and confirm the service is up."
            ),
        )
    # Look for loopback-only binding
    loopback_only = all("127.0.0.1:11434" in l for l in listening_lines)
    bound_all = any(
        "*:11434" in l or "0.0.0.0:11434" in l or ":::11434" in l
        for l in listening_lines
    )
    if loopback_only and not bound_all:
        return Result(
            name="ollama binding",
            status=Status.FAIL,
            message="bound to 127.0.0.1 only — containers can't reach it",
            fix=(
                "sudo mkdir -p /etc/systemd/system/ollama.service.d\n"
                "echo '[Service]\n"
                "Environment=\"OLLAMA_HOST=0.0.0.0\"' | \\\n"
                "  sudo tee /etc/systemd/system/ollama.service.d/override.conf\n"
                "sudo systemctl daemon-reload && sudo systemctl restart ollama"
            ),
        )
    return Result(
        name="ollama binding",
        status=Status.OK,
        message="listening on all interfaces",
    )


def check_bridge_to_ollama() -> Result:
    """From a container on the default bridge, can we reach the host's Ollama?

    This is the definitive test. It catches both the 127.0.0.1 binding issue
    and firewall rules (ufw, firewalld) that block the bridge subnet.
    """
    prefix = _docker_cmd_prefix()
    if prefix is None:
        return Result(
            name="bridge → ollama",
            status=Status.SKIP,
            message="docker not available",
        )

    cmd = [
        *prefix, "run", "--rm",
        "--add-host=host.docker.internal:host-gateway",
        "--entrypoint=wget",
        "alpine",
        "-qO-", "--timeout=5",
        "http://host.docker.internal:11434/api/version",
    ]
    rc, out, err = _run(cmd, timeout=45)
    if rc == 0 and out.strip().startswith("{"):
        return Result(
            name="bridge → ollama",
            status=Status.OK,
            message="container can reach host:11434",
        )
    return Result(
        name="bridge → ollama",
        status=Status.FAIL,
        message="container cannot reach host Ollama",
        detail=((err or out).strip().splitlines() or [""])[0],
        fix=(
            "Two likely causes:\n"
            "(a) Ollama bound to 127.0.0.1 — see the 'ollama binding' fix above.\n"
            "(b) Host firewall (ufw) blocking the docker bridge:\n"
            "    sudo ufw allow from 172.17.0.0/16 to any port 11434 proto tcp\n"
            "    sudo ufw reload"
        ),
    )


def check_ollama_model(url: str, model: str) -> Result:
    """Confirm the named model is pulled in Ollama."""
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return Result(
            name=f"model {model}",
            status=Status.SKIP,
            message=f"cannot query Ollama ({e})",
        )
    names = [m.get("name") for m in data.get("models") or []]
    if model in names:
        return Result(
            name=f"model {model}",
            status=Status.OK,
            message="pulled",
        )
    return Result(
        name=f"model {model}",
        status=Status.FAIL,
        message="not pulled",
        detail=f"available models: {', '.join(names) if names else '(none)'}",
        fix=f"ollama pull {model}",
    )


def check_workspace_dir(path: Path) -> Result:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".nursery-preflight-probe"
        probe.write_text("ok")
        probe.unlink()
        return Result(
            name="workspace",
            status=Status.OK,
            message=f"writable ({path})",
        )
    except OSError as e:
        return Result(
            name="workspace",
            status=Status.FAIL,
            message=f"not writable: {path}",
            detail=str(e),
        )


# ---------------------------------------------------------------------------
# Preflight runners
# ---------------------------------------------------------------------------


def _parse_model(model: str) -> tuple[str, str]:
    """ 'ollama/batiai/gemma4-e2b:q4' → ('ollama', 'batiai/gemma4-e2b:q4') """
    if "/" not in model:
        return ("", model)
    provider, _, name = model.partition("/")
    return provider, name


def _gateway_url_for_host(host_profile_name: str) -> str:
    """The Ollama URL the spawned container will use, per host profile env."""
    # Mirrors HOST_PROFILES default_env values in lifecycle.py.
    return "http://host.docker.internal:11434"


def _host_probe_url() -> str:
    """Reach the host's Ollama from the CLI (which is running on the host)."""
    return "http://127.0.0.1:11434"


def run_doctor() -> Report:
    """Full standalone readiness report. No spec required."""
    report = Report()
    report.add(check_docker())
    report.add(check_host_gateway_resolution())
    report.add(check_ollama_local(_host_probe_url()))
    report.add(check_ollama_binding())
    report.add(check_bridge_to_ollama())
    return report


def run_preflight_for_spawn(spec: dict, workspace: Path) -> Report:
    """Checks run right before `nursery spawn`. Targeted at this spec."""
    report = Report()
    report.add(check_docker())
    report.add(check_workspace_dir(workspace))

    model = spec.get("model") or ""
    provider, model_name = _parse_model(model)
    if provider == "ollama":
        report.add(check_ollama_local(_host_probe_url()))
        report.add(check_ollama_binding())
        report.add(check_bridge_to_ollama())
        if model_name:
            report.add(check_ollama_model(_host_probe_url(), model_name))
    else:
        report.add(Result(
            name=f"backend ({provider or 'unknown'})",
            status=Status.SKIP,
            message="no preflight checks implemented for this backend yet",
        ))
    return report


def run_post_spawn_verify(
    agent_url: str,
    *,
    timeout_s: float = 30.0,
    poll_interval_s: float = 1.0,
) -> Report:
    """After docker run, poll the container's /healthz until backend_ok or timeout."""
    report = Report()
    deadline = time.monotonic() + timeout_s
    last_info: dict | None = None
    last_err: str | None = None

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{agent_url}/healthz", timeout=2) as r:
                info = json.loads(r.read().decode("utf-8"))
            last_info = info
            if info.get("ok") and info.get("backend_ok"):
                report.add(Result(
                    name="container healthy",
                    status=Status.OK,
                    message=f"{info.get('name')} ready (backend_ok=true)",
                ))
                return report
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            # Includes ConnectionRefusedError, ConnectionResetError,
            # and transient errors while the HTTP server is still binding.
            last_err = str(e)
        time.sleep(poll_interval_s)

    if last_info and last_info.get("ok") and not last_info.get("backend_ok"):
        report.add(Result(
            name="container healthy",
            status=Status.FAIL,
            message="container is up but its backend is unreachable",
            detail=(
                "The agent started and HTTP is responding, but it cannot reach Ollama.\n"
                "Run `nursery doctor` to diagnose, then restart the container."
            ),
            fix=(
                "nursery logs <agent-name>        # see runtime errors\n"
                "nursery doctor                   # diagnose the host\n"
                "# fix whatever's red, then:\n"
                "nursery rm <agent-name> && nursery spawn <spec>"
            ),
        ))
    else:
        report.add(Result(
            name="container healthy",
            status=Status.FAIL,
            message=f"container did not respond within {timeout_s:.0f}s",
            detail=last_err or "no /healthz response observed",
            fix=(
                "nursery logs <agent-name>        # see what happened on boot"
            ),
        ))
    return report
