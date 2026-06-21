from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from upnote_to_apple_notes.extractor import extract_notes


@pytest.fixture
def fixture_db_path(tmp_path: Path) -> Path:
    database_path = tmp_path / "upnote.sqlite3"
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE notebooks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                parent TEXT,
                deleted INTEGER DEFAULT 0
            );

            CREATE TABLE notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                html TEXT NOT NULL,
                createdAt DOUBLE NOT NULL,
                updatedAt DOUBLE NOT NULL,
                tagLinks TEXT NOT NULL DEFAULT '[]',
                deleted INTEGER DEFAULT 0,
                trashed INTEGER DEFAULT 0
            );

            CREATE TABLE tags (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                deleted INTEGER DEFAULT 0
            );

            CREATE TABLE organizers (
                id TEXT PRIMARY KEY,
                noteId TEXT NOT NULL,
                notebookId TEXT NOT NULL,
                deleted INTEGER DEFAULT 0
            );
            """
        )
        connection.executemany(
            "INSERT INTO notebooks (id, title, parent) VALUES (?, ?, ?)",
            [
                ("notebook-3", "Projects", None),
                ("notebook-2", "Work", None),
                ("notebook-1", "Personal", "notebook-3"),
            ],
        )
        connection.executemany(
            "INSERT INTO notes (id, title, html, createdAt, updatedAt, tagLinks) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("note-2", "Second note", "content-2", 1704186000.0, 1704358800.0, "[\"beta\"]"),
                ("note-1", "First note", "content-1", 1704100000.0, 1704272400.0, "[\"beta\", \"alpha\"]"),
                ("note-3", "Third note", "content-3", 1704101000.0, 1704273400.0, "[]"),
            ],
        )
        connection.executemany(
            "INSERT INTO tags (id, title) VALUES (?, ?)",
            [
                ("tag-1", "#alpha"),
                ("tag-2", "#beta"),
            ],
        )
        connection.executemany(
            "INSERT INTO organizers (id, noteId, notebookId) VALUES (?, ?, ?)",
            [
                ("notebook-2:note-2", "note-2", "notebook-2"),
                ("notebook-1:note-1", "note-1", "notebook-1"),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    return database_path


def test_extract_notes_reads_notebook_name_and_note_source_id(fixture_db_path: Path):
    result = extract_notes(fixture_db_path)

    assert [notebook.name for notebook in result.notebooks] == ["Personal", "Projects", "Work"]
    assert [notebook.source_id for notebook in result.notebooks] == ["notebook-1", "notebook-3", "notebook-2"]


def test_extract_notes_reads_notebook_parent_relationships(fixture_db_path: Path):
    result = extract_notes(fixture_db_path)

    assert [
        (notebook.source_id, notebook.parent_id) for notebook in result.notebooks
    ] == [
        ("notebook-1", "notebook-3"),
        ("notebook-3", None),
        ("notebook-2", None),
    ]


def test_extract_notes_reads_note_title_tags_and_source_id(fixture_db_path: Path):
    result = extract_notes(fixture_db_path)

    assert [note.title for note in result.notes] == ["First note", "Third note", "Second note"]
    assert [note.source_id for note in result.notes] == ["note-1", "note-3", "note-2"]
    assert [note.tags for note in result.notes] == [["#beta", "#alpha"], [], ["#beta"]]


def test_extract_notes_keeps_active_notes_without_notebook_assignment(fixture_db_path: Path):
    result = extract_notes(fixture_db_path)

    assert [(note.source_id, note.notebook_id) for note in result.notes] == [
        ("note-1", "notebook-1"),
        ("note-3", None),
        ("note-2", "notebook-2"),
    ]
