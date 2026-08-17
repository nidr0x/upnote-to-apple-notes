from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import upnote_to_apple_notes.extractor as extractor
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
                space TEXT,
                deleted INTEGER DEFAULT 0
            );

            CREATE TABLE notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                html TEXT NOT NULL,
                createdAt DOUBLE NOT NULL,
                updatedAt DOUBLE NOT NULL,
                tagLinks TEXT NOT NULL DEFAULT '[]',
                space TEXT,
                noteLinks TEXT NOT NULL DEFAULT '[]',
                fileIds TEXT NOT NULL DEFAULT '[]',
                pinned INTEGER DEFAULT 0,
                bookmarked INTEGER DEFAULT 0,
                isTemplate INTEGER DEFAULT 0,
                rtl INTEGER DEFAULT 0,
                deleted INTEGER DEFAULT 0,
                trashed INTEGER DEFAULT 0
            );

            CREATE TABLE workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                deleted INTEGER DEFAULT 0
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
        connection.execute("INSERT INTO workspaces (id, name) VALUES ('space-1', 'Team Space')")
        connection.execute("UPDATE notebooks SET space = 'space-1' WHERE id = 'notebook-2'")
        connection.executemany(
            "INSERT INTO notes (id, title, html, createdAt, updatedAt, tagLinks) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("note-2", "Second note", "content-2", 1704186000.0, 1704358800.0, "[\"beta\"]"),
                ("note-1", "First note", "content-1", 1704100000.0, 1704272400.0, "[\"beta\", \"alpha\"]"),
                ("note-3", "Third note", "content-3", 1704101000.0, 1704273400.0, "[]"),
            ],
        )
        connection.execute(
            """
            UPDATE notes
            SET space = 'space-1', noteLinks = '["note-1"]',
                fileIds = '["file-1"]', pinned = 1
            WHERE id = 'note-2'
            """
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


def test_extract_notes_preserves_workspace_links_files_and_flags(fixture_db_path: Path):
    result = extract_notes(fixture_db_path)
    note = next(note for note in result.notes if note.source_id == "note-2")

    assert [(workspace.source_id, workspace.name) for workspace in result.workspaces] == [
        ("space-1", "Team Space")
    ]
    assert note.workspace_id == "space-1"
    assert note.note_links == ["note-1"]
    assert note.file_ids == ["file-1"]
    assert note.pinned is True


def test_extract_notes_reports_macos_database_permission_denial(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def deny(*args, **kwargs):
        raise sqlite3.OperationalError("unable to open database file: authorization denied")

    monkeypatch.setattr(extractor.sqlite3, "connect", deny)

    with pytest.raises(extractor.SourceAccessError, match="Full Disk Access"):
        extract_notes(tmp_path / "upnote.sqlite3")
