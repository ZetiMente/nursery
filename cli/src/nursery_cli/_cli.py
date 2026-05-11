"""nursery CLI entry point — turnkey reproducible AI agents."""

from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

__version__ = "0.2.0"


def _find_schema() -> Path:
    """Locate the agent schema.

    Resolution order:
      1. Bundled with the package (installed mode).
      2. ../spec/agent.schema.json relative to this file (dev/repo mode).
      3. $NURSERY_SCHEMA environment variable (escape hatch).
    """
    import os

    env_override = os.environ.get("NURSERY_SCHEMA")
    if env_override:
        p = Path(env_override)
        if p.exists():
            return p

    # Bundled package resource
    try:
        with resources.as_file(
            resources.files("nursery_cli").joinpath("agent.schema.json")
        ) as p:
            if p.exists():
                return p
    except (ModuleNotFoundError, FileNotFoundError):
        pass

    # Dev mode: walk up from this file to find the repo's spec/ dir
    here = Path(__file__).resolve()
    for ancestor in (here.parent, *here.parents):
        candidate = ancestor / "spec" / "agent.schema.json"
        if candidate.exists():
            return candidate

    sys.stderr.write(
        "error: could not locate agent.schema.json.\n"
        "       Set NURSERY_SCHEMA=<path> or reinstall the package.\n"
    )
    sys.exit(2)


def _load_yaml(path: Path) -> dict:
    """Parse a YAML (or JSON) file into a dict. Errors bubble up."""
    try:
        import yaml  # type: ignore
    except ImportError:
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text())
        sys.stderr.write(
            "error: PyYAML is required to read YAML specs.\n"
            "       This should be installed automatically — if you see this, the\n"
            "       install is broken. Try: uv tool install --force nursery-cli\n"
        )
        sys.exit(2)

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_schema() -> dict:
    schema_path = _find_schema()
    return json.loads(schema_path.read_text())


def _validate(spec: dict, schema: dict) -> list[str]:
    """Validate spec against schema. Returns a list of human-readable errors."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        sys.stderr.write(
            "error: jsonschema is required for validation.\n"
            "       This should be installed automatically — reinstall the package.\n"
        )
        sys.exit(2)

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(spec), key=lambda e: list(e.absolute_path))
    out: list[str] = []
    for err in errors:
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"  at {path}: {err.message}")
    return out


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.spec).resolve()
    if not path.exists():
        sys.stderr.write(f"error: spec file not found: {path}\n")
        return 2

    try:
        spec = _load_yaml(path)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"error: failed to parse {path}: {e}\n")
        return 2

    if not isinstance(spec, dict):
        sys.stderr.write("error: spec must be a mapping (key/value structure)\n")
        return 2

    schema = _load_schema()
    errors = _validate(spec, schema)

    if errors:
        print(f"✗ {path} — {len(errors)} issue(s):")
        for e in errors:
            print(e)
        return 1

    name = spec.get("name", "<unnamed>")
    print(f"✓ {path}")
    print(f"  agent: {name}")
    print(f"  image: {spec.get('image')}")
    print(f"  model: {spec.get('model')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nursery",
        description="Turnkey reproducible AI agents.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"nursery {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sp_val = subparsers.add_parser(
        "validate",
        help="Validate an agent spec against the schema.",
    )
    sp_val.add_argument("spec", help="Path to an agent spec (.yaml, .yml, or .json).")
    sp_val.set_defaults(func=cmd_validate)

    # Lifecycle commands: spawn, ps, stop, rm, logs
    from nursery_cli.lifecycle import register_subparsers as _register_lifecycle
    _register_lifecycle(subparsers)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
