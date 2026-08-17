from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ExtractionResult, NotebookRecord, NoteRecord, WorkspaceRecord


class SourceAccessError(RuntimeError):
    """Raised when macOS exposes the database path but denies its contents."""


def _open_read_only_connection(database_path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(
            f"file:{database_path.resolve()}?mode=ro", uri=True
        )
    except sqlite3.OperationalError as error:
        if "authorization denied" in str(error).lower() or "unable to open" in str(error).lower():
            raise SourceAccessError(
                "macOS denied access to the UpNote database. Grant Full Disk Access "
                "to Terminal or Codex in System Settings > Privacy & Security, "
                "then run discover and extract again."
            ) from error
        raise
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


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def _optional_column(columns: set[str], name: str) -> str:
    return name if name in columns else f"NULL AS {name}"


def extract_notes(database_path: Path) -> ExtractionResult:
    connection = _open_read_only_connection(database_path)
    try:
        workspaces = []
        if _table_exists(connection, "workspaces"):
            workspaces = [
                WorkspaceRecord(source_id=str(row["id"]), name=str(row["name"] or ""))
                for row in connection.execute(
                    """
                    SELECT id, name
                    FROM workspaces
                    WHERE deleted = 0 OR deleted IS NULL
                    ORDER BY name
                    """
                )
            ]

        notebook_columns = _table_columns(connection, "notebooks")
        notebooks = [
            NotebookRecord(
                source_id=str(row["id"]),
                name=str(row["title"]),
                parent_id=str(row["parent"]) if row["parent"] else None,
                workspace_id=str(row["space"]) if row["space"] else None,
            )
            for row in connection.execute(
                f"""
                SELECT id, title, parent, {_optional_column(notebook_columns, 'space')}
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
        note_columns = _table_columns(connection, "notes")

        notes = []
        for row in connection.execute(
            f"""
            SELECT id, title, html, createdAt, updatedAt, tagLinks,
                   {_optional_column(note_columns, 'space')},
                   {_optional_column(note_columns, 'noteLinks')},
                   {_optional_column(note_columns, 'fileIds')},
                   {_optional_column(note_columns, 'pinned')},
                   {_optional_column(note_columns, 'bookmarked')},
                   {_optional_column(note_columns, 'isTemplate')},
                   {_optional_column(note_columns, 'rtl')}
            FROM notes
            WHERE (deleted = 0 OR deleted IS NULL)
              AND (trashed = 0 OR trashed IS NULL)
            ORDER BY updatedAt
            """
        ):
            note_id = str(row["id"])

            tags = []
            for raw_tag in _decode_json_list(row["tagLinks"]):
                tags.append(tag_title_map.get(raw_tag, raw_tag))

            notes.append(
                NoteRecord(
                    source_id=note_id,
                    notebook_id=notebook_by_note_id.get(note_id),
                    title=str(row["title"] or ""),
                    raw_content=str(row["html"] or ""),
                    created_at=str(row["createdAt"]),
                    updated_at=str(row["updatedAt"]),
                    tags=tags,
                    workspace_id=str(row["space"]) if row["space"] else None,
                    note_links=_decode_json_list(row["noteLinks"]),
                    file_ids=_decode_json_list(row["fileIds"]),
                    pinned=bool(row["pinned"]),
                    bookmarked=bool(row["bookmarked"]),
                    is_template=bool(row["isTemplate"]),
                    rtl=bool(row["rtl"]),
                )
            )

        return ExtractionResult(
            notebooks=notebooks, notes=notes, workspaces=workspaces
        )
    finally:
        connection.close()
