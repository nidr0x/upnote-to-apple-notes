from __future__ import annotations

import json
from pathlib import Path
import pytest

from upnote_to_apple_notes.models import (
    ExtractionResult,
    NotebookRecord,
    NoteRecord,
    WorkspaceRecord,
)
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
    assert manifest["notes"][0]["notebook_path"] == ["Personal"]
    assert manifest["notes"][0]["fingerprint"]
    assert note_html_path.read_text() == "<p>raw html body</p>"


def test_write_export_tree_fails_when_note_notebook_is_missing(tmp_path: Path) -> None:
    extraction = ExtractionResult(
        notebooks=[],
        notes=[
            NoteRecord(
                source_id=1,
                notebook_id=10,
                title="Note 1",
                raw_content="<p>raw html body</p>",
                created_at="2024-01-01T09:00:00Z",
                updated_at="2024-01-02T09:00:00Z",
                tags=[],
            )
        ],
    )

    with pytest.raises(ValueError, match="notebook_id 10"):
        write_export_tree(extraction, tmp_path)

    assert not (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "notes").exists()
    assert not (tmp_path / "raw").exists()


def test_write_export_tree_writes_nested_notebook_path_and_root_note(tmp_path: Path) -> None:
    extraction = ExtractionResult(
        notebooks=[
            NotebookRecord(source_id="root", name="Clients"),
            NotebookRecord(source_id="child", name="Invoices", parent_id="root"),
        ],
        notes=[
            NoteRecord(
                source_id="foldered",
                notebook_id="child",
                title="Invoice",
                raw_content="<p>invoice</p>",
                created_at="1",
                updated_at="2",
                tags=[],
            ),
            NoteRecord(
                source_id="root-note",
                notebook_id=None,
                title="Inbox",
                raw_content="<p>inbox</p>",
                created_at="3",
                updated_at="4",
                tags=[],
            ),
        ],
    )

    manifest = write_export_tree(extraction, tmp_path)

    assert manifest.notes[0].notebook_path == ["Clients", "Invoices"]
    assert manifest.notes[1].notebook_path == []


def test_write_export_tree_fails_for_broken_notebook_parent(tmp_path: Path) -> None:
    extraction = ExtractionResult(
        notebooks=[
            NotebookRecord(source_id="child", name="Invoices", parent_id="missing")
        ],
        notes=[],
    )

    with pytest.raises(ValueError, match="missing parent_id missing"):
        write_export_tree(extraction, tmp_path)


def test_write_export_tree_rewrites_copied_local_image_urls(tmp_path: Path) -> None:
    source_root = tmp_path / "upnote"
    source_image = source_root / "images" / "image.jpg"
    source_image.parent.mkdir(parents=True)
    source_image.write_bytes(b"image")
    extraction = ExtractionResult(
        notebooks=[],
        notes=[
            NoteRecord(
                source_id="note-1",
                notebook_id=None,
                title="Image note",
                raw_content='<img src="http://localhost:9425/images/image.jpg">',
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-02T00:00:00Z",
            )
        ],
    )

    manifest = write_export_tree(extraction, tmp_path / "export", source_root)

    exported_image = tmp_path / "export" / "assets" / "images" / "image.jpg"
    assert exported_image.read_bytes() == b"image"
    assert exported_image.as_uri() in (tmp_path / "export" / "notes" / "note-note-1.html").read_text()
    assert manifest.assets.copied_files == 1


def test_write_export_tree_does_not_delete_existing_assets(tmp_path: Path) -> None:
    source_root = tmp_path / "upnote"
    (source_root / "images").mkdir(parents=True)
    (source_root / "images" / "current.jpg").write_bytes(b"current")
    export_root = tmp_path / "export"
    stale_asset = export_root / "assets" / "images" / "stale.jpg"
    stale_asset.parent.mkdir(parents=True)
    stale_asset.write_bytes(b"stale")

    write_export_tree(ExtractionResult(notebooks=[], notes=[]), export_root, source_root)

    assert stale_asset.read_bytes() == b"stale"
    assert (export_root / "assets" / "images" / "current.jpg").read_bytes() == b"current"


def test_write_export_tree_can_prefix_notebooks_with_workspace(tmp_path: Path) -> None:
    extraction = ExtractionResult(
        workspaces=[WorkspaceRecord(source_id="space-1", name="Team Space")],
        notebooks=[
            NotebookRecord(
                source_id="notebook-1",
                name="Projects",
                workspace_id="space-1",
            )
        ],
        notes=[
            NoteRecord(
                source_id="note-1",
                notebook_id="notebook-1",
                workspace_id="space-1",
                title="Plan",
                raw_content="<p>Plan</p>",
                created_at="1",
                updated_at="2",
                note_links=["note-2"],
                file_ids=["file-1"],
            )
        ],
    )

    manifest = write_export_tree(
        extraction, tmp_path / "export", spaces_as_folders=True
    )

    assert manifest.notes[0].notebook_path == ["Team Space", "Projects"]
    raw = json.loads((tmp_path / "export" / "raw" / "note-note-1.json").read_text())
    assert raw["note_links"] == ["note-2"]
    assert raw["file_ids"] == ["file-1"]
