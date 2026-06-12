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
