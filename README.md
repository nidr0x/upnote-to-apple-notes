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

## Commands

```bash
upnote-to-apple-notes discover
upnote-to-apple-notes extract --export-root ./export
upnote-to-apple-notes import --export-root ./export --mode dry-run
upnote-to-apple-notes resume --export-root ./export
upnote-to-apple-notes report --export-root ./export
```

## Development

Run the test suite with:

```bash
UV_CACHE_DIR=.uv-cache uv run --with pytest pytest -v
```

## Repository Layout

- `src/upnote_to_apple_notes/`: importer package
- `src/upnote_to_apple_notes/jxa/`: Apple Notes JXA script
- `tests/`: focused unit and integration smoke tests
- `docs/superpowers/specs/`: design spec
- `docs/superpowers/plans/`: implementation plan
