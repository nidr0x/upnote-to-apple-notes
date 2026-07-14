# UpNote to Apple Notes

CLI importer that reads the local UpNote macOS database and creates corresponding notes in Apple Notes.

## Run a Migration

Run these commands from the repository root. Do **not** drag `export/` into Apple Notes: it contains internal JSON, HTML, state, and report files.

### 1. Choose the destination account

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes accounts
```

Copy the exact account name shown, for example `nidr0x@icloud.com`.

### 2. Export UpNote

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes discover
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes extract --export-root ./export
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes preflight --export-root ./export
```

`preflight` must report `"ready": true`. It also reports copied assets and any local image references it could not resolve.

### 3. Import into Apple Notes

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes import \
  --export-root ./export \
  --account "nidr0x@icloud.com" \
  --mode skip-existing \
  --batch-size 50
```

This creates the UpNote notebook hierarchy directly under the selected account. Notes without a notebook go at the account root.

### 4. Verify the result

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes verify \
  --export-root ./export \
  --account "nidr0x@icloud.com"

UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes report --export-root ./export
```

`verify` checks every exported UpNote source ID against Apple Notes. `report` shows created, updated, and failed notes with retry counts.

### 5. Resume safely

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes resume \
  --export-root ./export \
  --account "nidr0x@icloud.com" \
  --batch-size 50
```

The importer saves state after every batch. If it is interrupted, `resume` retries failures without recreating completed notes.

## What Is Preserved

- Nested notebook/category hierarchy
- Note titles and HTML bodies
- Original UpNote creation and modification dates
- UpNote tags as Apple Notes `#tags`
- Local image and blob-storage files referenced by UpNote's local URLs
- A visible `UpNote source: upnote:<id>` footer for duplicate prevention, updates, and verification

Apple Notes has no scriptable custom metadata field. The source footer is visible deliberately: Notes strips HTML comments, which would make a hidden marker unreliable.

## Update Changed Notes

After exporting again, apply only notes whose title, body, or tags changed:

```bash
UV_CACHE_DIR=.uv-cache uv run upnote-to-apple-notes import \
  --export-root ./export \
  --account "nidr0x@icloud.com" \
  --mode update-changed
```

## Export Directory

`export/` is internal importer output, not a Finder import folder:

- `notes/`: normalized HTML note bodies
- `assets/`: copied UpNote local images and blobs
- `raw/`: raw debug records
- `manifest.json`: normalized manifest
- `state/`: resumable importer state
- `reports/`: importer reports

## Tests

```bash
UV_CACHE_DIR=.uv-cache uv run --with pytest pytest -v
```

`UV_CACHE_DIR=.uv-cache` keeps the uv cache inside the repository. `uv run --with pytest` installs pytest only for that run.
