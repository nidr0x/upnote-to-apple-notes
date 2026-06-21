from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from upnote_to_apple_notes.apple_notes import build_jxa_payload, run_jxa_import
from upnote_to_apple_notes.models import ExportManifest, ExportNoteRecord


def test_build_jxa_payload_includes_folder_path_and_provenance_marker_for_a_note(
    tmp_path: Path,
):
    manifest = ExportManifest(
        notes=[
            ExportNoteRecord(
                source_id=42,
                title="Imported note",
                notebook_path=["Work", "Project X"],
                tags=["alpha"],
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-02T00:00:00Z",
                html_path=Path("notes") / "note-42.html",
                raw_path=Path("raw") / "note-42.json",
                fingerprint="abc123",
                provenance_marker="upnote:42",
            )
        ],
        counts={"notes": 1, "notebooks": 1},
    )

    payload = build_jxa_payload(manifest, tmp_path)

    assert payload == {
        "notes": [
            {
                "source_id": 42,
                "title": "Imported note",
                "folder": ["Work", "Project X"],
                "html_path": str(tmp_path / "notes" / "note-42.html"),
                "marker": "upnote:42",
            }
        ]
    }


def test_build_jxa_payload_includes_empty_folder_path_for_root_note(tmp_path: Path):
    manifest = ExportManifest(
        notes=[
            ExportNoteRecord(
                source_id="root-note",
                title="Root note",
                notebook_path=[],
                tags=[],
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-02T00:00:00Z",
                html_path=Path("notes") / "note-root.html",
                raw_path=Path("raw") / "note-root.json",
                fingerprint="root123",
                provenance_marker="upnote:root-note",
            )
        ],
        counts={"notes": 1, "notebooks": 0},
    )

    payload = build_jxa_payload(manifest, tmp_path)

    assert payload["notes"][0]["folder"] == []


def test_run_jxa_import_raises_when_launcher_fails_without_stdout(monkeypatch: pytest.MonkeyPatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="",
            stderr="execution error",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="execution error"):
        run_jxa_import(Path("import_notes.js"), {"notes": []})
