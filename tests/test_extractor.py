from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from upnote_to_apple_notes.extractor import extract_notes


@pytest.fixture
def fixture_db_path(tmp_path: Path) -> Path:
    database_path = tmp_path / "UpNote.sqlite"
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE folders (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE notes (
                id INTEGER PRIMARY KEY,
                folder_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                raw_content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE tags (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE note_tags (
                note_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO folders (id, name) VALUES (?, ?)",
            [
                (2, "Work"),
                (1, "Personal"),
            ],
        )
        connection.executemany(
            "INSERT INTO notes (id, folder_id, title, raw_content, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (20, 2, "Second note", "content-2", "2024-01-02T09:00:00Z", "2024-01-04T09:00:00Z"),
                (10, 1, "First note", "content-1", "2024-01-01T09:00:00Z", "2024-01-03T09:00:00Z"),
            ],
        )
        connection.executemany(
            "INSERT INTO tags (id, name) VALUES (?, ?)",
            [
                (1, "alpha"),
                (2, "beta"),
            ],
        )
        connection.executemany(
            "INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)",
            [
                (10, 2),
                (10, 1),
                (20, 2),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    return database_path


def test_extract_notes_reads_notebook_name_and_note_source_id(fixture_db_path: Path):
    result = extract_notes(fixture_db_path)

    assert [notebook.name for notebook in result.notebooks] == ["Personal", "Work"]
    assert [notebook.source_id for notebook in result.notebooks] == [1, 2]


def test_extract_notes_reads_note_title_tags_and_source_id(fixture_db_path: Path):
    result = extract_notes(fixture_db_path)

    assert [note.title for note in result.notes] == ["First note", "Second note"]
    assert [note.source_id for note in result.notes] == [10, 20]
    assert [note.tags for note in result.notes] == [["beta", "alpha"], ["beta"]]
