from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import (
    ExportManifest,
    ExportNoteRecord,
    ExtractionResult,
)


def build_fingerprint(title: str, body: str, tags: list[str]) -> str:
    payload = json.dumps(
        {"title": title, "body": body, "tags": tags},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_export_tree(extraction: ExtractionResult, export_root: Path) -> ExportManifest:
    export_root.mkdir(parents=True, exist_ok=True)
    notes_dir = export_root / "notes"
    raw_dir = export_root / "raw"
    notes_dir.mkdir(exist_ok=True)
    raw_dir.mkdir(exist_ok=True)

    notebook_paths = {notebook.source_id: [notebook.name] for notebook in extraction.notebooks}
    notes: list[ExportNoteRecord] = []

    for note in extraction.notes:
        html_path = Path("notes") / f"note-{note.source_id}.html"
        raw_path = Path("raw") / f"note-{note.source_id}.json"
        fingerprint = build_fingerprint(note.title, note.raw_content, note.tags)
        provenance_marker = f"upnote:{note.source_id}"
        notebook_path = notebook_paths.get(note.notebook_id, [])

        (export_root / html_path).write_text(note.raw_content, encoding="utf-8")
        (export_root / raw_path).write_text(
            json.dumps(
                {
                    "source_id": note.source_id,
                    "notebook_id": note.notebook_id,
                    "title": note.title,
                    "raw_content": note.raw_content,
                    "created_at": note.created_at,
                    "updated_at": note.updated_at,
                    "tags": note.tags,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        notes.append(
            ExportNoteRecord(
                source_id=note.source_id,
                title=note.title,
                notebook_path=notebook_path,
                tags=note.tags,
                created_at=note.created_at,
                updated_at=note.updated_at,
                html_path=html_path,
                raw_path=raw_path,
                fingerprint=fingerprint,
                provenance_marker=provenance_marker,
            )
        )

    manifest = ExportManifest(
        notes=notes,
        counts={"notes": len(extraction.notes), "notebooks": len(extraction.notebooks)},
    )
    (export_root / "manifest.json").write_text(
        json.dumps(
            {
                "notes": [
                    {
                        "source_id": record.source_id,
                        "title": record.title,
                        "notebook_path": record.notebook_path,
                        "tags": record.tags,
                        "created_at": record.created_at,
                        "updated_at": record.updated_at,
                        "html_path": str(record.html_path),
                        "raw_path": str(record.raw_path),
                        "fingerprint": record.fingerprint,
                        "provenance_marker": record.provenance_marker,
                    }
                    for record in manifest.notes
                ],
                "counts": manifest.counts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest
