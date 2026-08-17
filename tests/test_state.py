from __future__ import annotations

from upnote_to_apple_notes.state import (
    ImportState,
    build_import_report,
    mark_note_status,
    should_import_note,
)


def test_mark_note_status_tracks_latest_status_and_attempts():
    state = ImportState()

    updated_state = mark_note_status(state, "note-1", "imported")
    updated_state = mark_note_status(updated_state, "note-1", "failed")

    assert "note-1" not in state.notes
    assert updated_state.notes["note-1"].status == "failed"
    assert updated_state.notes["note-1"].attempts == 2


def test_mark_note_status_records_destination_ledger_fields():
    state = mark_note_status(
        ImportState(),
        "note-1",
        "created",
        destination_id="x-coredata://note-1",
        destination_folder=["Work", "Project"],
        session_id="session-1",
    )

    assert state.notes["note-1"].destination_id == "x-coredata://note-1"
    assert state.notes["note-1"].destination_folder == ["Work", "Project"]
    assert state.notes["note-1"].session_id == "session-1"
    assert state.notes["note-1"].created_by_importer is False


def test_note_state_round_trips_rollback_guard_fields():
    state = mark_note_status(
        ImportState(),
        "note-1",
        "created",
        session_id="session-1",
        created_by_importer=True,
        destination_title="Title",
        destination_updated_at="2026-08-17T10:00:00Z",
    )

    from pathlib import Path
    import tempfile
    from upnote_to_apple_notes.state import load_state, save_state

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "state.json"
        save_state(path, state)
        restored = load_state(path)

    note = restored.notes["note-1"]
    assert note.created_by_importer is True
    assert note.destination_title == "Title"
    assert note.destination_updated_at == "2026-08-17T10:00:00Z"


def test_should_import_note_respects_skip_existing_and_update_changed():
    state = ImportState(
        notes={
            "note-1": {
                "status": "imported",
                "attempts": 1,
                "fingerprint": "abc",
            }
        }
    )

    assert should_import_note(state, "note-2", "xyz", "skip-existing") is True
    assert should_import_note(state, "note-1", "abc", "skip-existing") is False
    assert should_import_note(state, "note-1", "abc", "update-changed") is False
    assert should_import_note(state, "note-1", "def", "update-changed") is True
    assert should_import_note(state, "note-1", "abc", "resume") is False
    assert should_import_note(
        ImportState(
            notes={
                "note-3": {
                    "status": "created",
                    "attempts": 1,
                    "fingerprint": "ghi",
                }
            }
        ),
        "note-3",
        "ghi",
        "resume",
    ) is False
    assert should_import_note(
        ImportState(
            notes={
                "note-4": {
                    "status": "updated",
                    "attempts": 1,
                    "fingerprint": "jkl",
                }
            }
        ),
        "note-4",
        "jkl",
        "resume",
    ) is False


def test_build_import_report_counts_statuses():
    state = ImportState(
        notes={
            "note-1": {"status": "imported", "attempts": 1, "fingerprint": "a"},
            "note-2": {"status": "failed", "attempts": 2, "fingerprint": "b"},
            "note-3": {"status": "imported", "attempts": 1, "fingerprint": "c"},
        }
    )

    report = build_import_report(state)

    assert report["counts"] == {"imported": 2, "failed": 1}
    assert len(report["notes"]) == 3
