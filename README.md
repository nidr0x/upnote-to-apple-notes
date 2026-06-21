# UpNote to Apple Notes

CLI importer that reads the local UpNote macOS database and creates notes in Apple Notes.

## Status

What works now:

- `discover`
- `extract`
- `import`
- `resume`
- `report`

## Most Important Rule

Do **not** manually import the whole `export/` folder into Apple Notes.

If you do that, Apple Notes will import internal files like:

- `raw/*.json`
- `manifest.json`
- importer state/report files

That is why you can end up with notes that look like raw JSON.

## How to Execute

From the repository root, use `uv run`:

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes discover
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes extract --export-root ./export
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes import --export-root ./export --mode skip-existing
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes resume --export-root ./export
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes report --export-root ./export
```

Run the tests with:

```bash
UV_CACHE_DIR=.uv-cache uv run --with pytest pytest -v
```

Why that command works:

- `UV_CACHE_DIR=.uv-cache` keeps uv's cache inside the repo
- `uv run --with pytest` installs `pytest` just for that run
- `pytest -v` runs the full suite with verbose test names

If you want the command available inside the repo venv:

```bash
uv sync
source .venv/bin/activate
upnote-to-apple-notes discover
```

## Recommended Workflow

### 1. Find the UpNote database

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes discover
```

This should print the SQLite path.

### 2. Extract the notes

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes extract --export-root ./export
```

This creates the internal export directory the importer uses.

### 3. Treat `export/` as internal output

`export/` is not meant to be dragged into Apple Notes by hand.

It contains:

- `notes/`: HTML note bodies
- `raw/`: raw debug records
- `manifest.json`: normalized manifest
- `state/`: importer state
- `reports/`: importer reports

### 4. Import into Apple Notes

Use the importer, not Finder drag-and-drop:

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes import --export-root ./export --mode skip-existing
```

What this does:

- reads `export/manifest.json`
- creates Apple Notes folders that match the UpNote notebook path
- places notes with no UpNote category directly in the Apple Notes account root
- skips notes already marked as imported in importer state

Current account behavior:

- notes are imported into the first Apple Notes account returned by `Notes.app`

Useful modes:

- `--mode skip-existing`: import notes that have not been marked as created yet
- `--mode update-changed`: retry notes whose exported fingerprint changed
- `--mode dry-run`: write importer state/report data without creating Apple Notes content

If you previously ran an older broken import and need to run the full migration again, remove:

```text
export/state/import-state.json
```

or use a fresh export root before rerunning the import. That resets importer tracking only. It does **not** delete existing Apple Notes content.

### 5. Resume or inspect results

Resume:

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes resume --export-root ./export
```

Read the latest report:

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes report --export-root ./export
```
