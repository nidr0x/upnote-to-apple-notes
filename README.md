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

## Current Reality

Right now, the project has two different layers:

1. A working **discovery + extraction** pipeline
2. An **Apple Notes adapter boundary** that is still minimal and not a complete end-user migration flow

That distinction matters:

- `discover` works
- `extract` works
- the generated `export/` tree is an **internal intermediate format**
- you should **not manually import the whole `export/` folder into Apple Notes**

If you import the full `export/` folder by hand, Apple Notes will ingest internal artifacts such as:

- `raw/*.json`
- `manifest.json`
- state and report files

That is why notes can appear as raw JSON instead of real note content.

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

## Recommended Workflow

### 1. Discover the UpNote database

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes discover
```

Expected result:

- prints the resolved local UpNote SQLite path

### 2. Extract to an intermediate export tree

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes extract --export-root ./export
```

Expected result:

- creates `./export/manifest.json`
- creates `./export/notes/*.html`
- creates `./export/raw/*.json`

### 3. Do not manually import `./export/` into Apple Notes

This is the most important rule.

Do **not** do this:

- drag the entire `export/` folder into Apple Notes
- import `raw/`
- import `manifest.json`

Those files are internal pipeline artifacts, not user-facing Apple Notes input.

### 4. Understand what `import` currently means

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes import --export-root ./export --mode dry-run
```

Today, `dry-run` is the safest supported mode. It:

- reads the manifest
- selects notes for import
- writes state/report files
- does **not** mutate Apple Notes

The non-dry-run Apple Notes path is still a minimal adapter boundary. It is present for development, but it is not yet documented here as a fully reliable end-user migration command.

## What The Export Folder Contains

`export/` is an intermediate working directory, not the final thing to hand to Apple Notes.

- `notes/`: HTML note bodies
- `raw/`: raw extracted note records for debugging
- `manifest.json`: normalized import manifest
- `state/`: importer state used for reruns/resume
- `reports/`: generated import reports

If you open or import `raw/*.json`, you will see JSON content like the screenshot you shared. That is expected for those files.

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
