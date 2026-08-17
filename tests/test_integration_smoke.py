from __future__ import annotations

import json
from pathlib import Path

import pytest

from upnote_to_apple_notes import cli
from upnote_to_apple_notes.models import ExtractionResult, NotebookRecord, NoteRecord
from upnote_to_apple_notes.state import load_state


def test_run_extract_writes_manifest_with_source_id_note_1_when_discovery_and_extraction_are_monkeypatched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_discover_default_source():
        class Source:
            database_path = Path("/tmp/UpNote.sqlite")

        return Source()

    def fake_extract_notes(database_path: Path) -> ExtractionResult:
        assert database_path == Path("/tmp/UpNote.sqlite")
        return ExtractionResult(
            notebooks=[NotebookRecord(source_id=10, name="Personal")],
            notes=[
                NoteRecord(
                    source_id=1,
                    notebook_id=10,
                    title="Note 1",
                    raw_content="<p>body</p>",
                    created_at="2024-01-01T00:00:00Z",
                    updated_at="2024-01-02T00:00:00Z",
                    tags=[],
                )
            ],
        )

    monkeypatch.setattr(cli, "discover_default_source", fake_discover_default_source)
    monkeypatch.setattr(cli, "extract_notes", fake_extract_notes)

    result = cli.run_extract(tmp_path)

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert result == tmp_path
    assert manifest["notes"][0]["source_id"] == 1


def test_run_import_dry_run_writes_state_without_calling_the_jxa_launcher_when_manifest_contains_one_note(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    export_root = tmp_path / "export"
    export_root.mkdir()
    script_path = tmp_path / "import_notes.js"
    state_path = tmp_path / "state.json"

    manifest = {
        "notes": [
            {
                "source_id": 1,
                "title": "Imported note",
                "notebook_path": ["Personal"],
                "tags": [],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "html_path": "notes/note-1.html",
                "raw_path": "raw/note-1.json",
                "fingerprint": "fingerprint-1",
                "provenance_marker": "upnote:1",
            }
        ],
        "counts": {"notes": 1, "notebooks": 1},
    }

    monkeypatch.setattr(cli, "load_manifest", lambda path: manifest)

    def fail_run_jxa_import(script_path: Path, payload: dict[str, object]) -> dict[str, object]:
        raise AssertionError("run_jxa_import should not be called in dry-run mode")

    monkeypatch.setattr(cli, "run_jxa_import", fail_run_jxa_import)

    result = cli.run_import(
        export_root=export_root,
        script_path=script_path,
        state_path=state_path,
        mode="dry-run",
    )

    state = load_state(state_path)
    assert result == 0
    assert state.notes["1"].status == "planned"
    assert state.notes["1"].fingerprint == "fingerprint-1"


def test_run_import_non_dry_run_only_marks_notes_reported_by_jxa_as_created(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    export_root = tmp_path / "export"
    export_root.mkdir()
    script_path = tmp_path / "import_notes.js"
    state_path = tmp_path / "state.json"

    manifest = {
        "notes": [
            {
                "source_id": 1,
                "title": "Imported note",
                "notebook_path": ["Personal"],
                "tags": [],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "html_path": "notes/note-1.html",
                "raw_path": "raw/note-1.json",
                "fingerprint": "fingerprint-1",
                "provenance_marker": "upnote:1",
            },
            {
                "source_id": 2,
                "title": "Retryable note",
                "notebook_path": ["Personal"],
                "tags": [],
                "created_at": "2024-01-03T00:00:00Z",
                "updated_at": "2024-01-04T00:00:00Z",
                "html_path": "notes/note-2.html",
                "raw_path": "raw/note-2.json",
                "fingerprint": "fingerprint-2",
                "provenance_marker": "upnote:2",
            },
        ],
        "counts": {"notes": 2, "notebooks": 1},
    }

    monkeypatch.setattr(cli, "load_manifest", lambda path: manifest)
    monkeypatch.setattr(
        cli,
        "run_jxa_import",
        lambda script_path, payload: {
            "notes": [
                {"source_id": 1, "status": "created", "marker": "upnote:1"},
                {"source_id": 2, "status": "failed", "marker": "upnote:2"},
            ],
            "returncode": 0,
        },
    )

    result = cli.run_import(
        export_root=export_root,
        script_path=script_path,
        state_path=state_path,
        mode="skip-existing",
    )

    state = load_state(state_path)
    assert result == 1
    assert state.notes["1"].status == "created"
    assert state.notes["1"].fingerprint == "fingerprint-1"
    assert state.notes["2"].status == "failed"
    assert state.notes["2"].fingerprint == "fingerprint-2"


def test_run_import_records_missing_jxa_outcome_as_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    export_root = tmp_path / "export"
    export_root.mkdir()
    manifest = {
        "notes": [
            {
                "source_id": "missing",
                "title": "Missing outcome",
                "notebook_path": [],
                "tags": [],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "html_path": "notes/missing.html",
                "raw_path": "raw/missing.json",
                "fingerprint": "missing-fingerprint",
                "provenance_marker": "upnote:missing",
            }
        ],
        "counts": {"notes": 1, "notebooks": 0},
    }
    monkeypatch.setattr(cli, "load_manifest", lambda path: manifest)
    monkeypatch.setattr(cli, "run_jxa_import", lambda script_path, payload: {"notes": []})

    result = cli.run_import(
        export_root, tmp_path / "import.js", tmp_path / "state.json", "skip-existing"
    )

    state = load_state(tmp_path / "state.json")
    assert result == 1
    assert state.notes["missing"].status == "failed"
    assert state.notes["missing"].error == "Apple Notes returned no result"


def test_run_import_checkpoints_batch_when_launcher_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    export_root = tmp_path / "export"
    export_root.mkdir()
    manifest = {
        "notes": [
            {
                "source_id": "crashed",
                "title": "Launcher crash",
                "notebook_path": [],
                "tags": [],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "html_path": "notes/crashed.html",
                "raw_path": "raw/crashed.json",
                "fingerprint": "crashed-fingerprint",
                "provenance_marker": "upnote:crashed",
            }
        ],
        "counts": {"notes": 1, "notebooks": 0},
    }
    monkeypatch.setattr(cli, "load_manifest", lambda path: manifest)
    monkeypatch.setattr(cli, "run_jxa_import", lambda script_path, payload: (_ for _ in ()).throw(RuntimeError("Notes quit")))

    result = cli.run_import(
        export_root, tmp_path / "import.js", tmp_path / "state.json", "skip-existing"
    )

    state = load_state(tmp_path / "state.json")
    assert result == 1
    assert state.notes["crashed"].status == "failed"
    assert "Notes quit" in state.notes["crashed"].error


def test_run_import_records_destination_ledger_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    export_root = tmp_path / "export"
    export_root.mkdir()
    manifest = {
        "notes": [
            {
                "source_id": "note-1",
                "title": "Imported",
                "notebook_path": ["Work"],
                "tags": [],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "html_path": "notes/note-1.html",
                "raw_path": "raw/note-1.json",
                "fingerprint": "fingerprint",
                "provenance_marker": "upnote:note-1",
            }
        ],
        "counts": {"notes": 1, "notebooks": 1},
    }
    monkeypatch.setattr(cli, "load_manifest", lambda path: manifest)
    monkeypatch.setattr(
        cli,
        "run_jxa_import",
        lambda script_path, payload: {
            "notes": [
                {
                    "source_id": "note-1",
                    "status": "created",
                    "destination_id": "x-coredata://note-1",
                    "folder_path": ["Work"],
                }
            ]
        },
    )

    assert cli.run_import(
        export_root,
        tmp_path / "import.js",
        tmp_path / "state.json",
        "skip-existing",
        session_id="session-1",
    ) == 0
    note_state = load_state(tmp_path / "state.json").notes["note-1"]
    assert note_state.destination_id == "x-coredata://note-1"
    assert note_state.destination_folder == ["Work"]
    assert note_state.session_id == "session-1"


def test_run_import_batches_notes_and_preserves_requested_account(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    export_root = tmp_path / "export"
    export_root.mkdir()
    manifest = {
        "notes": [
            {
                "source_id": note_id,
                "title": f"Note {note_id}",
                "notebook_path": [],
                "tags": ["#work"],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "html_path": f"notes/note-{note_id}.html",
                "raw_path": f"raw/note-{note_id}.json",
                "fingerprint": f"fingerprint-{note_id}",
                "provenance_marker": f"upnote:{note_id}",
            }
            for note_id in range(3)
        ],
        "counts": {"notes": 3, "notebooks": 0},
    }
    monkeypatch.setattr(cli, "load_manifest", lambda path: manifest)
    payloads: list[dict[str, object]] = []

    def fake_run_jxa_import(script_path: Path, payload: dict[str, object]) -> dict[str, object]:
        payloads.append(payload)
        return {
            "notes": [
                {"source_id": note["source_id"], "status": "created"}
                for note in payload["notes"]
            ]
        }

    monkeypatch.setattr(cli, "run_jxa_import", fake_run_jxa_import)

    assert cli.run_import(
        export_root, tmp_path / "import_notes.js", tmp_path / "state.json", "skip-existing", "iCloud", 2
    ) == 0
    assert [len(payload["notes"]) for payload in payloads] == [2, 1]
    assert all(payload["account_name"] == "iCloud" for payload in payloads)


def test_run_preflight_reports_missing_html_and_assets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest = {
        "notes": [
            {"source_id": "present", "html_path": "notes/present.html", "tags": ["#work"]},
            {"source_id": "missing", "html_path": "notes/missing.html", "tags": ["#home"]},
        ],
        "counts": {"notebooks": 2},
        "assets": {"copied_files": 12},
    }
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "present.html").write_text("<p>present</p>", encoding="utf-8")
    monkeypatch.setattr(cli, "load_manifest", lambda path: manifest)

    report = cli.run_preflight(tmp_path)

    assert report == {
        "notes": 2,
        "notebooks": 2,
        "unique_tags": 2,
        "copied_assets": 12,
        "missing_html": ["missing"],
        "missing_assets": [],
        "ready": False,
        "capabilities": {
            "workspaces": {"detected": 0, "mapping": "metadata-only"},
            "internal_links": {"detected": 0, "mapping": "ledger-preserved"},
            "file_links": {"detected": 0, "mapping": "asset-copy"},
            "unsupported_metadata": {
                "pinned": 0,
                "bookmarked": 0,
                "is_template": 0,
                "rtl": 0,
            },
        },
    }


def test_run_verify_compares_content_metadata_and_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "note-1.html").write_text(
        '<p>Hello world</p><img src="file:///image.jpg">', encoding="utf-8"
    )
    manifest = {
        "notes": [
            {
                "source_id": "note-1",
                "title": "A note",
                "notebook_path": ["Work"],
                "tags": ["#important"],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "html_path": "notes/note-1.html",
                "provenance_marker": "upnote:note-1",
            }
        ]
    }
    monkeypatch.setattr(cli, "load_manifest", lambda path: manifest)
    monkeypatch.setattr(
        cli,
        "run_jxa_import",
        lambda script_path, payload: {
            "notes": {
                "upnote:note-1": [
                    {
                        "destination_id": "apple-1",
                        "title": "A note",
                        "body": (
                            '<div>Hello world</div><img src="cid:image">'
                            "<p>#important</p><p>UpNote source: upnote:note-1</p>"
                        ),
                        "folder_path": ["Work"],
                        "created_at": "2024-01-01T00:00:00.000Z",
                        "updated_at": "2024-01-02T00:00:00.000Z",
                    }
                ]
            }
        },
    )

    report = cli.run_verify(tmp_path, tmp_path / "import.js", "iCloud")

    assert report == {
        "expected": 1,
        "matched": 1,
        "missing": [],
        "duplicates": [],
        "mismatched": [],
        "ready": True,
    }


def test_run_verify_reports_missing_duplicate_and_mismatched_notes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "notes").mkdir()
    for source_id in ("missing", "duplicate", "mismatch"):
        (tmp_path / "notes" / f"{source_id}.html").write_text("<p>body</p>")
    notes = [
        {
            "source_id": source_id,
            "title": source_id,
            "notebook_path": [],
            "tags": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "html_path": f"notes/{source_id}.html",
            "provenance_marker": f"upnote:{source_id}",
        }
        for source_id in ("missing", "duplicate", "mismatch")
    ]
    monkeypatch.setattr(cli, "load_manifest", lambda path: {"notes": notes})
    destination = {
        "destination_id": "apple",
        "title": "wrong title",
        "body": "<p>wrong body</p>",
        "folder_path": ["wrong folder"],
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
    }
    monkeypatch.setattr(
        cli,
        "run_jxa_import",
        lambda script_path, payload: {
            "notes": {
                "upnote:missing": [],
                "upnote:duplicate": [destination, destination],
                "upnote:mismatch": [destination],
            }
        },
    )

    report = cli.run_verify(tmp_path, tmp_path / "import.js", None)

    assert report["ready"] is False
    assert report["missing"] == ["missing"]
    assert report["duplicates"] == ["duplicate"]
    assert report["mismatched"][0]["source_id"] == "mismatch"
    assert set(report["mismatched"][0]["reasons"]) >= {
        "title",
        "folder",
        "body",
        "provenance",
        "created-at",
        "updated-at",
    }
