from __future__ import annotations

import json
from pathlib import Path

from upnote_to_apple_notes.models import ExtractionResult, NotebookRecord, NoteRecord
from upnote_to_apple_notes.normalize import write_export_tree


def test_write_export_tree_writes_manifest_and_note_html(tmp_path: Path) -> None:
    extraction = ExtractionResult(
        notebooks=[NotebookRecord(source_id=10, name="Personal")],
        notes=[
            NoteRecord(
                source_id=1,
                notebook_id=10,
                title="Note 1",
                raw_content="<p>raw html body</p>",
                created_at="2024-01-01T09:00:00Z",
                updated_at="2024-01-02T09:00:00Z",
                tags=["alpha"],
            )
        ],
    )

    write_export_tree(extraction, tmp_path)

    manifest_path = tmp_path / "manifest.json"
    note_html_path = tmp_path / "notes" / "note-1.html"

    assert manifest_path.exists()
    assert note_html_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["counts"]["notes"] == 1
    assert manifest["counts"]["notebooks"] == 1
    assert manifest["notes"][0]["fingerprint"]
    assert note_html_path.read_text() == "<p>raw html body</p>"
