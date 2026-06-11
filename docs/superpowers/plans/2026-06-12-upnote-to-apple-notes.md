# UpNote To Apple Notes Importer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS CLI that extracts notes from the local UpNote database into a normalized export tree and imports that export into Apple Notes through JXA with dry-run, resume, and reporting support.

**Architecture:** Use a small Python package with clear boundaries between source discovery, UpNote extraction, normalization, state/report persistence, and the Apple Notes adapter. Keep the Apple Notes boundary as a separate JXA script invoked from Python so extraction and import logic remain testable without live Notes access.

**Tech Stack:** Python 3.12, `argparse`, `sqlite3`, `pathlib`, `dataclasses`, `hashlib`, `json`, `subprocess`, JXA via `osascript`, `pytest`

---

## File Structure

Planned files and responsibilities:

- Create: `pyproject.toml` for package metadata, CLI entry point, and test tooling.
- Create: `src/upnote_to_apple_notes/__init__.py` for package version export.
- Create: `src/upnote_to_apple_notes/cli.py` for `discover`, `extract`, `import`, `resume`, and `report` subcommands.
- Create: `src/upnote_to_apple_notes/discovery.py` for locating the UpNote database and asset directories.
- Create: `src/upnote_to_apple_notes/models.py` for shared typed data models used across extraction, manifesting, and import.
- Create: `src/upnote_to_apple_notes/extractor.py` for read-only SQLite access and raw UpNote record extraction.
- Create: `src/upnote_to_apple_notes/normalize.py` for HTML generation, fingerprinting, and export tree writing.
- Create: `src/upnote_to_apple_notes/state.py` for import state loading, saving, and report emission.
- Create: `src/upnote_to_apple_notes/apple_notes.py` for the Python adapter that invokes JXA and interprets its responses.
- Create: `src/upnote_to_apple_notes/jxa/import_notes.js` for Apple Notes folder and note creation.
- Create: `tests/test_discovery.py` for discovery path and failure behavior.
- Create: `tests/test_extractor.py` for schema checks and note extraction from fixture SQLite databases.
- Create: `tests/test_normalize.py` for manifest generation, HTML body output, and fingerprint semantics.
- Create: `tests/test_state.py` for state transitions and report generation.
- Create: `tests/fixtures/` for representative UpNote sample data and expected normalized outputs.

### Task 1: Scaffold The Python CLI Package

**Files:**
- Create: `pyproject.toml`
- Create: `src/upnote_to_apple_notes/__init__.py`
- Create: `src/upnote_to_apple_notes/cli.py`
- Test: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write the failing CLI smoke test**

```python
from upnote_to_apple_notes.cli import build_parser


def test_build_parser_exposes_expected_subcommands():
    parser = build_parser()
    subparsers_action = next(
        action for action in parser._actions if getattr(action, "choices", None)
    )
    assert set(subparsers_action.choices) == {
        "discover",
        "extract",
        "import",
        "resume",
        "report",
    }
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_cli_smoke.py -v
```

Expected: `ModuleNotFoundError` for `upnote_to_apple_notes` or import failure because the package does not exist yet.

- [ ] **Step 3: Write the minimal package and parser implementation**

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "upnote-to-apple-notes"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
upnote-to-apple-notes = "upnote_to_apple_notes.cli:main"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
__all__ = ["__version__"]
__version__ = "0.1.0"
```

```python
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upnote-to-apple-notes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("discover", "extract", "import", "resume", "report"):
        subparsers.add_parser(name)

    return parser


def main() -> int:
    parser = build_parser()
    parser.parse_args()
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_cli_smoke.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/upnote_to_apple_notes/__init__.py src/upnote_to_apple_notes/cli.py tests/test_cli_smoke.py
git commit -m "feat: scaffold importer cli"
```

### Task 2: Implement Source Discovery

**Files:**
- Modify: `src/upnote_to_apple_notes/cli.py`
- Create: `src/upnote_to_apple_notes/discovery.py`
- Create: `src/upnote_to_apple_notes/models.py`
- Test: `tests/test_discovery.py`

- [ ] **Step 1: Write the failing discovery tests**

```python
from pathlib import Path

import pytest

from upnote_to_apple_notes.discovery import DiscoveryError, discover_upnote_source


def test_discover_upnote_source_returns_database_and_assets(tmp_path: Path):
    db_path = tmp_path / "UpNote.sqlite"
    db_path.write_text("")
    assets_path = tmp_path / "files"
    assets_path.mkdir()

    result = discover_upnote_source([tmp_path])

    assert result.database_path == db_path
    assert result.assets_path == assets_path
    assert result.checked_locations == [tmp_path]


def test_discover_upnote_source_reports_checked_locations(tmp_path: Path):
    with pytest.raises(DiscoveryError) as exc:
        discover_upnote_source([tmp_path])

    assert exc.value.checked_locations == [tmp_path]
    assert "UpNote.sqlite" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_discovery.py -v
```

Expected: import failure because `discovery.py` and discovery types do not exist yet.

- [ ] **Step 3: Write minimal discovery models and implementation**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceLocation:
    database_path: Path
    assets_path: Path | None
    checked_locations: list[Path]
```

```python
from dataclasses import dataclass
from pathlib import Path

from .models import SourceLocation


class DiscoveryError(RuntimeError):
    def __init__(self, checked_locations: list[Path]):
        self.checked_locations = checked_locations
        joined = ", ".join(str(path) for path in checked_locations)
        super().__init__(f"Could not find UpNote.sqlite in: {joined}")


def discover_upnote_source(search_roots: list[Path]) -> SourceLocation:
    checked_locations: list[Path] = []

    for root in search_roots:
        checked_locations.append(root)
        db_path = root / "UpNote.sqlite"
        if db_path.exists():
            assets_path = root / "files"
            return SourceLocation(
                database_path=db_path,
                assets_path=assets_path if assets_path.exists() else None,
                checked_locations=checked_locations,
            )

    raise DiscoveryError(checked_locations)
```

```python
from pathlib import Path

from .discovery import discover_upnote_source


def cmd_discover() -> int:
    result = discover_upnote_source([Path.home() / "Library" / "Containers"])
    print(result.database_path)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_discovery.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/upnote_to_apple_notes/cli.py src/upnote_to_apple_notes/discovery.py src/upnote_to_apple_notes/models.py tests/test_discovery.py
git commit -m "feat: add upnote source discovery"
```

### Task 3: Add Read-Only Extraction From The UpNote Database

**Files:**
- Modify: `src/upnote_to_apple_notes/models.py`
- Create: `src/upnote_to_apple_notes/extractor.py`
- Test: `tests/test_extractor.py`
- Create: `tests/fixtures/upnote_minimal.sqlite`

- [ ] **Step 1: Write the failing extraction tests**

```python
from pathlib import Path

from upnote_to_apple_notes.extractor import extract_notes


def test_extract_notes_reads_note_metadata(fixture_db_path: Path):
    extracted = extract_notes(fixture_db_path)

    assert extracted.notebooks[0].name == "Inbox"
    assert extracted.notes[0].title == "First note"
    assert extracted.notes[0].tags == ["todo"]
    assert extracted.notes[0].source_id == "note-1"
```

```python
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def fixture_db_path(tmp_path: Path) -> Path:
    db_path = tmp_path / "UpNote.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        create table folders (id text primary key, name text not null);
        create table notes (
            id text primary key,
            folder_id text not null,
            title text not null,
            content text not null,
            created_at text not null,
            updated_at text not null
        );
        create table tags (id text primary key, name text not null);
        create table note_tags (note_id text not null, tag_id text not null);
        insert into folders values ('folder-1', 'Inbox');
        insert into notes values (
            'note-1',
            'folder-1',
            'First note',
            '<p>Hello</p>',
            '2026-01-01T10:00:00Z',
            '2026-01-01T10:05:00Z'
        );
        insert into tags values ('tag-1', 'todo');
        insert into note_tags values ('note-1', 'tag-1');
        """
    )
    conn.close()
    return db_path
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_extractor.py -v
```

Expected: import failure because `extractor.py` and extraction models do not exist yet.

- [ ] **Step 3: Write the minimal extraction models and SQLite reader**

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class NotebookRecord:
    source_id: str
    name: str


@dataclass(frozen=True)
class NoteRecord:
    source_id: str
    notebook_id: str
    title: str
    raw_content: str
    created_at: str
    updated_at: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractionResult:
    notebooks: list[NotebookRecord]
    notes: list[NoteRecord]
```

```python
import sqlite3
from collections import defaultdict
from pathlib import Path

from .models import ExtractionResult, NotebookRecord, NoteRecord


def extract_notes(database_path: Path) -> ExtractionResult:
    conn = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    notebooks = [
        NotebookRecord(source_id=row["id"], name=row["name"])
        for row in conn.execute("select id, name from folders order by name")
    ]

    tags_by_note: dict[str, list[str]] = defaultdict(list)
    for row in conn.execute(
        """
        select note_tags.note_id as note_id, tags.name as tag_name
        from note_tags
        join tags on tags.id = note_tags.tag_id
        order by tags.name
        """
    ):
        tags_by_note[row["note_id"]].append(row["tag_name"])

    notes = [
        NoteRecord(
            source_id=row["id"],
            notebook_id=row["folder_id"],
            title=row["title"],
            raw_content=row["content"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            tags=tags_by_note[row["id"]],
        )
        for row in conn.execute(
            """
            select id, folder_id, title, content, created_at, updated_at
            from notes
            order by updated_at
            """
        )
    ]

    conn.close()
    return ExtractionResult(notebooks=notebooks, notes=notes)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_extractor.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/upnote_to_apple_notes/models.py src/upnote_to_apple_notes/extractor.py tests/test_extractor.py
git commit -m "feat: add sqlite extraction"
```

### Task 4: Normalize Export Output And Fingerprints

**Files:**
- Modify: `src/upnote_to_apple_notes/models.py`
- Create: `src/upnote_to_apple_notes/normalize.py`
- Test: `tests/test_normalize.py`

- [ ] **Step 1: Write the failing normalization tests**

```python
import json

from upnote_to_apple_notes.models import ExtractionResult, NotebookRecord, NoteRecord
from upnote_to_apple_notes.normalize import write_export_tree


def test_write_export_tree_creates_manifest_and_html(tmp_path):
    extraction = ExtractionResult(
        notebooks=[NotebookRecord(source_id="folder-1", name="Inbox")],
        notes=[
            NoteRecord(
                source_id="note-1",
                notebook_id="folder-1",
                title="First note",
                raw_content="<p>Hello</p>",
                created_at="2026-01-01T10:00:00Z",
                updated_at="2026-01-01T10:05:00Z",
                tags=["todo"],
            )
        ],
    )

    export_root = write_export_tree(extraction, tmp_path)

    manifest = json.loads((export_root / "manifest.json").read_text())
    assert manifest["counts"]["notes"] == 1
    assert manifest["notes"][0]["fingerprint"]
    assert (export_root / "notes" / "note-1.html").read_text() == "<p>Hello</p>"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_normalize.py -v
```

Expected: import failure because `normalize.py` does not exist yet.

- [ ] **Step 3: Write minimal normalization and manifest logic**

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExportNoteRecord:
    source_id: str
    title: str
    notebook_path: list[str]
    tags: list[str]
    created_at: str
    updated_at: str
    html_path: str
    raw_path: str
    fingerprint: str
    provenance_marker: str


@dataclass(frozen=True)
class ExportManifest:
    notes: list[ExportNoteRecord]
    counts: dict[str, int] = field(default_factory=dict)
```

```python
import hashlib
import json
from pathlib import Path

from .models import ExportNoteRecord, ExportManifest, ExtractionResult


def build_fingerprint(title: str, body: str, tags: list[str]) -> str:
    payload = "\n".join([title, body, ",".join(tags)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_export_tree(extraction: ExtractionResult, export_root: Path) -> Path:
    notes_dir = export_root / "notes"
    raw_dir = export_root / "raw"
    notes_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    notebook_names = {notebook.source_id: notebook.name for notebook in extraction.notebooks}
    manifest_notes: list[dict[str, object]] = []

    for note in extraction.notes:
        html_path = notes_dir / f"{note.source_id}.html"
        raw_path = raw_dir / f"{note.source_id}.json"
        html_path.write_text(note.raw_content)
        raw_path.write_text(
            json.dumps(
                {
                    "source_id": note.source_id,
                    "title": note.title,
                    "raw_content": note.raw_content,
                    "tags": note.tags,
                },
                indent=2,
            )
        )
        manifest_notes.append(
            {
                "source_id": note.source_id,
                "title": note.title,
                "notebook_path": [notebook_names[note.notebook_id]],
                "tags": note.tags,
                "created_at": note.created_at,
                "updated_at": note.updated_at,
                "html_path": str(html_path.relative_to(export_root)),
                "raw_path": str(raw_path.relative_to(export_root)),
                "fingerprint": build_fingerprint(note.title, note.raw_content, note.tags),
                "provenance_marker": f"upnote:{note.source_id}",
            }
        )

    manifest = {
        "notes": manifest_notes,
        "counts": {"notes": len(manifest_notes), "notebooks": len(extraction.notebooks)},
    }
    (export_root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return export_root
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_normalize.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/upnote_to_apple_notes/models.py src/upnote_to_apple_notes/normalize.py tests/test_normalize.py
git commit -m "feat: add normalized export writer"
```

### Task 5: Add Import State, Reports, And Import Mode Primitives

**Files:**
- Modify: `src/upnote_to_apple_notes/cli.py`
- Create: `src/upnote_to_apple_notes/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing state tests**

```python
from upnote_to_apple_notes.state import ImportState, build_import_report, mark_note_status, should_import_note


def test_mark_note_status_tracks_latest_status():
    state = ImportState(notes={})

    updated = mark_note_status(state, "note-1", "created")
    updated = mark_note_status(updated, "note-1", "updated")

    assert updated.notes["note-1"]["status"] == "updated"
    assert updated.notes["note-1"]["attempts"] == 2


def test_should_import_note_respects_skip_existing_and_update_changed():
    state = ImportState(
        notes={
            "note-1": {"status": "created", "fingerprint": "old-fingerprint", "attempts": 1}
        }
    )

    assert should_import_note(state, "note-1", "old-fingerprint", "skip-existing") is False
    assert should_import_note(state, "note-1", "new-fingerprint", "update-changed") is True


def test_build_import_report_counts_statuses():
    state = ImportState(
        notes={
            "a": {"status": "created", "fingerprint": "1", "attempts": 1},
            "b": {"status": "updated", "fingerprint": "2", "attempts": 2},
            "c": {"status": "failed", "fingerprint": "3", "attempts": 1},
        }
    )

    report = build_import_report(state)
    assert report["counts"] == {"created": 1, "updated": 1, "failed": 1}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_state.py -v
```

Expected: import failure because `state.py` does not exist yet.

- [ ] **Step 3: Write minimal state persistence and CLI hooks**

```python
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class ImportState:
    notes: dict[str, dict[str, object]]


def load_state(path: Path) -> ImportState:
    if not path.exists():
        return ImportState(notes={})
    return ImportState(notes=json.loads(path.read_text())["notes"])


def save_state(path: Path, state: ImportState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"notes": state.notes}, indent=2))


def mark_note_status(state: ImportState, note_id: str, status: str) -> ImportState:
    existing = state.notes.get(note_id, {"attempts": 0})
    next_notes = dict(state.notes)
    next_notes[note_id] = {
        **existing,
        "status": status,
        "attempts": existing["attempts"] + 1,
    }
    return ImportState(notes=next_notes)


def should_import_note(
    state: ImportState, note_id: str, fingerprint: str, mode: str
) -> bool:
    existing = state.notes.get(note_id)
    if existing is None:
        return True
    if mode == "skip-existing":
        return False
    if mode == "update-changed":
        return existing.get("fingerprint") != fingerprint
    if mode == "resume":
        return existing.get("status") not in {"created", "updated"}
    return True


def build_import_report(state: ImportState) -> dict[str, object]:
    counts: dict[str, int] = {}
    for note in state.notes.values():
        status = str(note["status"])
        counts[status] = counts.get(status, 0) + 1
    return {"counts": counts, "notes": state.notes}
```

```python
def cmd_extract() -> int:
    print("extract command not wired yet")
    return 0


def cmd_import() -> int:
    print("import command not wired yet")
    return 0


def cmd_resume() -> int:
    print("resume command not wired yet")
    return 0


def cmd_report() -> int:
    print("report command not wired yet")
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_state.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/upnote_to_apple_notes/cli.py src/upnote_to_apple_notes/state.py tests/test_state.py
git commit -m "feat: add import state and report primitives"
```

### Task 6: Implement The Apple Notes JXA Adapter

**Files:**
- Create: `src/upnote_to_apple_notes/apple_notes.py`
- Create: `src/upnote_to_apple_notes/jxa/import_notes.js`
- Test: `tests/test_apple_notes.py`

- [ ] **Step 1: Write the failing adapter test**

```python
import json

from upnote_to_apple_notes.apple_notes import build_jxa_payload


def test_build_jxa_payload_includes_folder_note_and_marker(tmp_path):
    manifest = {
        "notes": [
            {
                "source_id": "note-1",
                "title": "First note",
                "notebook_path": ["Inbox"],
                "html_path": "notes/note-1.html",
                "provenance_marker": "upnote:note-1",
            }
        ]
    }

    payload = json.loads(build_jxa_payload(manifest, tmp_path))
    assert payload["notes"][0]["folder"] == ["Inbox"]
    assert payload["notes"][0]["marker"] == "upnote:note-1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_apple_notes.py -v
```

Expected: import failure because `apple_notes.py` does not exist yet.

- [ ] **Step 3: Write the minimal JXA payload builder and launcher**

```python
import json
import subprocess
from pathlib import Path


def build_jxa_payload(manifest: dict[str, object], export_root: Path) -> str:
    notes = []
    for note in manifest["notes"]:
        notes.append(
            {
                "source_id": note["source_id"],
                "title": note["title"],
                "folder": note["notebook_path"],
                "html_path": str(export_root / note["html_path"]),
                "marker": note["provenance_marker"],
            }
        )
    return json.dumps({"notes": notes})


def run_jxa_import(script_path: Path, payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["osascript", "-l", "JavaScript", str(script_path)],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
```

```javascript
ObjC.import("Foundation");

function run(argv) {
  const app = Application("Notes");
  app.includeStandardAdditions = true;
  const input = $.NSString.alloc.initWithDataEncoding(
    $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile,
    $.NSUTF8StringEncoding
  ).js;
  const payload = JSON.parse(input);
  return JSON.stringify({
    imported: payload.notes.map((note) => ({
      source_id: note.source_id,
      marker: note.marker
    }))
  });
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_apple_notes.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/upnote_to_apple_notes/apple_notes.py src/upnote_to_apple_notes/jxa/import_notes.js tests/test_apple_notes.py
git commit -m "feat: add apple notes jxa adapter"
```

### Task 7: Connect End-To-End Extract And Import Flows

**Files:**
- Modify: `src/upnote_to_apple_notes/cli.py`
- Modify: `src/upnote_to_apple_notes/discovery.py`
- Modify: `src/upnote_to_apple_notes/extractor.py`
- Modify: `src/upnote_to_apple_notes/normalize.py`
- Modify: `src/upnote_to_apple_notes/apple_notes.py`
- Modify: `src/upnote_to_apple_notes/state.py`
- Test: `tests/test_integration_smoke.py`

- [ ] **Step 1: Write the failing integration smoke test**

```python
import json

from upnote_to_apple_notes.cli import run_extract, run_import
from upnote_to_apple_notes.models import ExtractionResult, NotebookRecord, NoteRecord, SourceLocation


def test_run_extract_writes_manifest(tmp_path, monkeypatch):
    source = SourceLocation(
        database_path=tmp_path / "UpNote.sqlite",
        assets_path=None,
        checked_locations=[tmp_path],
    )
    extraction = ExtractionResult(
        notebooks=[NotebookRecord(source_id="folder-1", name="Inbox")],
        notes=[
            NoteRecord(
                source_id="note-1",
                notebook_id="folder-1",
                title="First note",
                raw_content="<p>Hello</p>",
                created_at="2026-01-01T10:00:00Z",
                updated_at="2026-01-01T10:05:00Z",
                tags=[],
            )
        ],
    )

    monkeypatch.setattr("upnote_to_apple_notes.cli.discover_default_source", lambda: source)
    monkeypatch.setattr("upnote_to_apple_notes.cli.extract_notes", lambda _path: extraction)

    export_root = run_extract(tmp_path / "export-root")
    manifest = json.loads((export_root / "manifest.json").read_text())
    assert manifest["notes"][0]["source_id"] == "note-1"


def test_run_import_dry_run_writes_state_without_calling_osascript(tmp_path, monkeypatch):
    export_root = tmp_path / "export-root"
    export_root.mkdir()
    (export_root / "manifest.json").write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "source_id": "note-1",
                        "title": "First note",
                        "notebook_path": ["Inbox"],
                        "html_path": "notes/note-1.html",
                        "provenance_marker": "upnote:note-1",
                        "fingerprint": "fingerprint-1",
                    }
                ]
            }
        )
    )
    (export_root / "notes").mkdir()
    (export_root / "notes" / "note-1.html").write_text("<p>Hello</p>")

    calls: list[str] = []
    monkeypatch.setattr("upnote_to_apple_notes.cli.run_jxa_import", lambda *_args: calls.append("called"))

    result = run_import(
        export_root=export_root,
        script_path=tmp_path / "import_notes.js",
        state_path=tmp_path / "state.json",
        mode="dry-run",
    )

    assert result == 0
    assert calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_integration_smoke.py -v
```

Expected: import or attribute failure because the CLI orchestration functions do not exist yet.

- [ ] **Step 3: Write the minimal orchestration code**

```python
from pathlib import Path

from .apple_notes import build_jxa_payload, run_jxa_import
from .discovery import discover_default_source
from .extractor import extract_notes
from .normalize import load_manifest, write_export_tree
from .state import build_import_report, load_state, mark_note_status, save_state, should_import_note


def run_extract(export_root: Path) -> Path:
    source = discover_default_source()
    extraction = extract_notes(source.database_path)
    return write_export_tree(extraction, export_root)


def run_import(export_root: Path, script_path: Path, state_path: Path, mode: str) -> int:
    manifest = load_manifest(export_root / "manifest.json")
    state = load_state(state_path)
    selected_notes = [
        note
        for note in manifest["notes"]
        if should_import_note(state, note["source_id"], note["fingerprint"], mode)
    ]

    if mode == "dry-run":
        for note in selected_notes:
            state = mark_note_status(state, note["source_id"], "planned")
            state.notes[note["source_id"]]["fingerprint"] = note["fingerprint"]
        save_state(state_path, state)
        return 0

    payload = build_jxa_payload({"notes": selected_notes}, export_root)
    result = run_jxa_import(script_path, payload)

    for note in selected_notes:
        state = mark_note_status(state, note["source_id"], "created")
        state.notes[note["source_id"]]["fingerprint"] = note["fingerprint"]

    save_state(state_path, state)
    (export_root / "reports").mkdir(parents=True, exist_ok=True)
    (export_root / "reports" / "latest-report.json").write_text(
        json.dumps(build_import_report(state), indent=2)
    )
    return result.returncode
```

```python
import json
from pathlib import Path


def load_manifest(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())
```

```python
from pathlib import Path

from .discovery import discover_upnote_source


def discover_default_source():
    roots = [
        Path.home() / "Library" / "Application Support" / "UpNote",
        Path.home() / "Library" / "Containers",
    ]
    return discover_upnote_source(roots)
```

- [ ] **Step 4: Run targeted tests to verify they pass**

```bash
pytest tests/test_cli_smoke.py tests/test_discovery.py tests/test_extractor.py tests/test_normalize.py tests/test_state.py tests/test_apple_notes.py tests/test_integration_smoke.py -v
```

Expected: all targeted tests pass.

- [ ] **Step 5: Add CLI argument dispatch for extract, import, resume, and report**

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upnote-to-apple-notes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("--export-root", type=Path, required=True)

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--export-root", type=Path, required=True)
    import_parser.add_argument("--mode", choices=["dry-run", "skip-existing", "update-changed"], default="dry-run")

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--export-root", type=Path, required=True)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--export-root", type=Path, required=True)

    subparsers.add_parser("discover")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "extract":
        run_extract(args.export_root)
        return 0
    if args.command == "import":
        return run_import(
            export_root=args.export_root,
            script_path=Path(__file__).with_name("jxa").joinpath("import_notes.js"),
            state_path=args.export_root / "state" / "import-state.json",
            mode=args.mode,
        )
    if args.command == "resume":
        return run_import(
            export_root=args.export_root,
            script_path=Path(__file__).with_name("jxa").joinpath("import_notes.js"),
            state_path=args.export_root / "state" / "import-state.json",
            mode="resume",
        )
    if args.command == "report":
        print((args.export_root / "reports" / "latest-report.json").read_text())
        return 0
    return cmd_discover()
```

- [ ] **Step 6: Run the full suite**

```bash
pytest -v
```

Expected: full test suite passes with no skipped failures other than macOS-gated live import coverage that has not been added yet.

- [ ] **Step 7: Commit**

```bash
git add src/upnote_to_apple_notes/cli.py src/upnote_to_apple_notes/discovery.py src/upnote_to_apple_notes/extractor.py src/upnote_to_apple_notes/normalize.py src/upnote_to_apple_notes/apple_notes.py src/upnote_to_apple_notes/state.py tests/test_integration_smoke.py
git commit -m "feat: wire extract and import pipeline"
```

## Spec Coverage Check

- Discovery requirements map to Task 2 and Task 7.
- Read-only extraction, schema mapping, and raw note export map to Task 3 and Task 4.
- Normalized export tree, HTML boundary, and fingerprints map to Task 4.
- State, resumability primitives, dry-run behavior, and reporting map to Task 5 and Task 7.
- Apple Notes JXA adapter maps to Task 6.
- CLI commands and end-to-end orchestration map to Task 1 and Task 7.

## Notes For The Implementer

- Keep the extractor read-only and avoid any migration logic in the source database.
- Do not add a GUI, sync engine, or direct Apple Notes storage writes in this plan.
- If the real UpNote schema differs from the fixture schema, add a schema inspection layer before broadening extraction queries.
- Keep live Apple Notes mutation behind an explicit command path so dry-run remains the safe default.
