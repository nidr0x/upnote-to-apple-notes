from __future__ import annotations

import argparse
from pathlib import Path

from .discovery import discover_upnote_source


def cmd_discover() -> int:
    source = discover_upnote_source([Path.home() / "Library" / "Containers"])
    print(source.database_path)
    return 0


def cmd_extract() -> int:
    return 0


def cmd_import() -> int:
    return 0


def cmd_resume() -> int:
    return 0


def cmd_report() -> int:
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upnote-to-apple-notes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("discover", "extract", "import", "resume", "report"):
        subparser = subparsers.add_parser(command)
        if command == "discover":
            subparser.set_defaults(func=cmd_discover)
        elif command == "extract":
            subparser.set_defaults(func=cmd_extract)
        elif command == "import":
            subparser.set_defaults(func=cmd_import)
        elif command == "resume":
            subparser.set_defaults(func=cmd_resume)
        elif command == "report":
            subparser.set_defaults(func=cmd_report)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    handler = getattr(args, "func", None)
    if handler is not None:
        return handler()
    return 0
