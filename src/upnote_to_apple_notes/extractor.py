from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import ExtractionResult, NotebookRecord, NoteRecord


def _open_read_only_connection(database_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{database_path.resolve()}?mode=ro", uri=True)


def extract_notes(database_path: Path) -> ExtractionResult:
    connection = _open_read_only_connection(database_path)
    try:
        notebooks = [
            NotebookRecord(source_id=row[0], name=row[1])
            for row in connection.execute(
                "SELECT id, name FROM folders ORDER BY name"
            )
        ]

        notes = []
        for row in connection.execute(
            """
            SELECT id, folder_id, title, raw_content, created_at, updated_at
            FROM notes
            ORDER BY updated_at
            """
        ):
            note_id = row[0]
            tags = [
                tag_row[0]
                for tag_row in connection.execute(
                    """
                    SELECT tags.name
                    FROM note_tags
                    JOIN tags ON tags.id = note_tags.tag_id
                    WHERE note_tags.note_id = ?
                    ORDER BY note_tags.rowid
                    """,
                    (note_id,),
                )
            ]
            notes.append(
                NoteRecord(
                    source_id=note_id,
                    notebook_id=row[1],
                    title=row[2],
                    raw_content=row[3],
                    created_at=row[4],
                    updated_at=row[5],
                    tags=tags,
                )
            )

        return ExtractionResult(notebooks=notebooks, notes=notes)
    finally:
        connection.close()
