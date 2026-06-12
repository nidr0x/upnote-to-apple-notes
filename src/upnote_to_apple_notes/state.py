from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class NoteState:
    status: str = "pending"
    attempts: int = 0
    fingerprint: str | None = None


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


def mark_note_status(state: ImportState, note_id: str, status: str) -> None:
    note = state.notes.setdefault(note_id, NoteState())
    note.status = status
    note.attempts += 1


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
    if mode == "update-changed":
        return note.fingerprint != fingerprint
    return True


def build_import_report(state: ImportState) -> dict[str, int]:
    counts: dict[str, int] = {}
    for note in state.notes.values():
        status = str(note.status)
        counts[status] = counts.get(status, 0) + 1
    return counts
