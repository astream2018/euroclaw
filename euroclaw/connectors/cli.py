"""Command-line interface for the connector generator.

Usage:
    python -m euroclaw.connectors.cli generate --description TEXT --out DIR
    python -m euroclaw.connectors.cli validate DIR
    python -m euroclaw.connectors.cli show DIR
"""

from __future__ import annotations

import argparse
import os
import sys

from euroclaw.connectors.generator import ConnectorGenerator
from euroclaw.connectors.spec import ConnectorManifest, validate_connector_dir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="euroclaw-connectors",
        description="Generate and validate AI-assisted connectors.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate a new connector scaffold.")
    gen.add_argument("--description", required=True, help="Natural-language spec.")
    gen.add_argument("--out", required=True, help="Target output directory.")

    val = sub.add_parser("validate", help="Validate a connector directory.")
    val.add_argument("dir", help="Connector directory to validate.")

    show = sub.add_parser("show", help="Print a connector manifest as YAML.")
    show.add_argument("dir", help="Connector directory to inspect.")

    return parser


def _cmd_generate(args) -> int:
    generator = ConnectorGenerator()
    manifest = generator.generate(args.description, args.out)
    print(f"Generated connector {manifest.name!r} in {args.out}")
    for filename in (
        "manifest.yaml",
        "connector.py",
        "test_connector.py",
        "README.md",
        ".pending-review",
    ):
        print("  " + os.path.join(args.out, filename))
    print(
        "\nREMINDER: this connector is AI-GENERATED and PENDING REVIEW. "
        "It is UNTRUSTED and must not be enabled until reviewed and the "
        "`.pending-review` marker is removed."
    )
    return 0


def _cmd_validate(args) -> int:
    problems = validate_connector_dir(args.dir)
    if not problems:
        print("OK")
        return 0
    print("Validation problems:")
    for problem in problems:
        print("  - " + problem)
    return 1


def _cmd_show(args) -> int:
    manifest_path = os.path.join(args.dir, "manifest.yaml")
    if not os.path.isfile(manifest_path):
        print(f"manifest.yaml not found in {args.dir}", file=sys.stderr)
        return 1
    try:
        manifest = ConnectorManifest.from_file(manifest_path)
    except Exception as exc:  # noqa: BLE001 - surface parse errors to the user
        print(f"Could not parse manifest: {exc}", file=sys.stderr)
        return 1
    print(manifest.to_yaml(), end="")
    return 0


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "generate":
        return _cmd_generate(args)
    if args.command == "validate":
        return _cmd_validate(args)
    if args.command == "show":
        return _cmd_show(args)
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
