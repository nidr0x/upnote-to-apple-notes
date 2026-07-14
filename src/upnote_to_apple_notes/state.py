from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

COMPLETED_NOTE_STATUSES = frozenset({"created", "imported", "skipped"})


@dataclass
class NoteState:
    status: str = "pending"
    attempts: int = 0
    fingerprint: str | None = None
    error: str | None = None


@dataclass
class ImportState:
    notes: dict[str, NoteState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.notes = {
            note_id: _coerce_note_state(note)
            for note_id, note in self.notes.items()
        }


def _coerce_note_state(note: NoteState | dict[str, object]) -> NoteState:
    if isinstance(note, NoteState):
        return note
    return NoteState(
        status=str(note.get("status", "pending")),
        attempts=int(note.get("attempts", 0)),
        fingerprint=note.get("fingerprint") if note.get("fingerprint") is not None else None,
        error=note.get("error") if note.get("error") is not None else None,
    )


def load_state(path: Path) -> ImportState:
    if not path.exists():
        return ImportState()

    payload = json.loads(path.read_text())
    notes = payload.get("notes", {})
    if not isinstance(notes, dict):
        notes = {}

    return ImportState(notes=notes)


def save_state(path: Path, state: ImportState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"notes": {note_id: asdict(note) for note_id, note in state.notes.items()}},
            indent=2,
            sort_keys=True,
        )
    )


def mark_note_status(
    state: ImportState, note_id: str, status: str, error: str | None = None
) -> ImportState:
    notes = {
        existing_note_id: NoteState(
            status=existing_note.status,
            attempts=existing_note.attempts,
            fingerprint=existing_note.fingerprint,
            error=existing_note.error,
        )
        for existing_note_id, existing_note in state.notes.items()
    }
    note = notes.get(note_id, NoteState())
    note.status = status
    note.attempts += 1
    note.error = error
    notes[note_id] = note
    return ImportState(notes=notes)


def should_import_note(
    state: ImportState,
    note_id: str,
    fingerprint: str,
    mode: str,
) -> bool:
    note = state.notes.get(note_id)
    if note is None:
        return True

    if mode == "skip-existing":
        return False
    if mode == "resume" and note.status in COMPLETED_NOTE_STATUSES:
        return False
    if mode == "update-changed":
        return note.fingerprint != fingerprint
    return True


def build_import_report(state: ImportState) -> dict[str, object]:
    counts: dict[str, int] = {}
    notes: list[dict[str, object]] = []
    for note_id, note in state.notes.items():
        status = str(note.status)
        counts[status] = counts.get(status, 0) + 1
        notes.append(
            {
                "note_id": note_id,
                "status": note.status,
                "attempts": note.attempts,
                "fingerprint": note.fingerprint,
                "error": note.error,
            }
        )
    return {"counts": counts, "notes": notes}
