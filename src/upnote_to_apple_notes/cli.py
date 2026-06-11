from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upnote-to-apple-notes")
    subparsers = parser.add_subparsers(dest="command")

    for command in ("discover", "extract", "import", "resume", "report"):
        subparsers.add_parser(command)

    return parser


def main() -> int:
    build_parser().parse_args()
    return 0
