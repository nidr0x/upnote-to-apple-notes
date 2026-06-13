# UpNote to Apple Notes

CLI importer for migrating notes from a local UpNote macOS database into Apple Notes.

## What It Does

- Discovers a local UpNote database on macOS
- Extracts notebooks, notes, and tags from SQLite in read-only mode
- Writes a normalized export tree with note HTML, raw records, and a manifest
- Prepares Apple Notes import payloads through a JXA adapter
- Supports dry-run import planning, resumability, and import reports

## Current Scope

This project is intentionally narrow and macOS-specific.

- Source: local UpNote app database
- Destination: Apple Notes through `osascript` + JXA
- Interface: CLI only

The Apple Notes automation layer is implemented as a minimal adapter boundary. It is suitable for development and extension, but it is not yet a fully production-hardened migration tool.

## Running the CLI

In a fresh clone, the `upnote-to-apple-notes` command is not installed globally, so this will fail:

```bash
upnote-to-apple-notes discover
```

Use `uv run` from the repository root instead:

```bash
uv run upnote-to-apple-notes discover
uv run upnote-to-apple-notes extract --export-root ./export
uv run upnote-to-apple-notes import --export-root ./export --mode dry-run
uv run upnote-to-apple-notes resume --export-root ./export
uv run upnote-to-apple-notes report --export-root ./export
```

If you prefer a local shell command during development, install the project into the repo virtual environment:

```bash
uv sync
source .venv/bin/activate
upnote-to-apple-notes discover
```

## Commands

The commands above are the supported entry points; use them through `uv run` unless you have already activated `.venv`.

## Development

Run the test suite with:

```bash
UV_CACHE_DIR=.uv-cache uv run --with pytest pytest -v
```

What this does:

- `UV_CACHE_DIR=.uv-cache` keeps uv's cache inside the repo instead of using a global cache path.
- `uv run --with pytest` creates or reuses an isolated environment with `pytest` available.
- `pytest -v` runs the full test suite in verbose mode.

If the first run says it is creating `.venv` or building the package, that is expected.

## Repository Layout

- `src/upnote_to_apple_notes/`: importer package
- `src/upnote_to_apple_notes/jxa/`: Apple Notes JXA script
- `tests/`: focused unit and integration smoke tests
- `docs/superpowers/specs/`: design spec
- `docs/superpowers/plans/`: implementation plan
