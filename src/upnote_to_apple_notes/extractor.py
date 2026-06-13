from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ExtractionResult, NotebookRecord, NoteRecord


def _open_read_only_connection(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{database_path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _load_tag_title_map(connection: sqlite3.Connection) -> dict[str, str]:
    tag_title_map: dict[str, str] = {}
    for row in connection.execute("SELECT id, title FROM tags WHERE deleted = 0 OR deleted IS NULL"):
        title = row["title"]
        if not title:
            continue
        normalized = str(title).lstrip("#")
        tag_title_map[normalized] = str(title)
        tag_title_map[str(row["id"])] = str(title)
    return tag_title_map


def _decode_json_list(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return [str(item) for item in decoded]
    return []


def extract_notes(database_path: Path) -> ExtractionResult:
    connection = _open_read_only_connection(database_path)
    try:
        notebooks = [
            NotebookRecord(source_id=str(row["id"]), name=str(row["title"]))
            for row in connection.execute(
                """
                SELECT id, title
                FROM notebooks
                WHERE deleted = 0 OR deleted IS NULL
                ORDER BY title
                """
            )
        ]

        notebook_by_note_id = {
            str(row["noteId"]): str(row["notebookId"])
            for row in connection.execute(
                """
                SELECT noteId, notebookId
                FROM organizers
                WHERE (deleted = 0 OR deleted IS NULL)
                  AND noteId IS NOT NULL
                  AND notebookId IS NOT NULL
                """
            )
        }
        tag_title_map = _load_tag_title_map(connection)

        notes = []
        for row in connection.execute(
            """
            SELECT id, title, html, createdAt, updatedAt, tagLinks
            FROM notes
            WHERE (deleted = 0 OR deleted IS NULL)
              AND (trashed = 0 OR trashed IS NULL)
            ORDER BY updatedAt
            """
        ):
            note_id = str(row["id"])
            notebook_id = notebook_by_note_id.get(note_id)
            if notebook_id is None:
                continue

            tags = []
            for raw_tag in _decode_json_list(row["tagLinks"]):
                tags.append(tag_title_map.get(raw_tag, raw_tag))

            notes.append(
                NoteRecord(
                    source_id=note_id,
                    notebook_id=notebook_id,
                    title=str(row["title"] or ""),
                    raw_content=str(row["html"] or ""),
                    created_at=str(row["createdAt"]),
                    updated_at=str(row["updatedAt"]),
                    tags=tags,
                )
            )

        return ExtractionResult(notebooks=notebooks, notes=notes)
    finally:
        connection.close()
