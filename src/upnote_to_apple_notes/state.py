from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

COMPLETED_NOTE_STATUSES = frozenset({"created", "updated", "imported", "skipped"})


@dataclass
class NoteState:
    status: str = "pending"
    attempts: int = 0
    fingerprint: str | None = None
    error: str | None = None
    destination_id: str | None = None
    destination_folder: list[str] = field(default_factory=list)
    session_id: str | None = None
    created_by_importer: bool = False
    destination_title: str | None = None
    destination_updated_at: str | None = None


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
        destination_id=(
            str(note["destination_id"])
            if note.get("destination_id") is not None
            else None
        ),
        destination_folder=[str(part) for part in note.get("destination_folder", [])],
        session_id=str(note["session_id"]) if note.get("session_id") is not None else None,
        created_by_importer=bool(note.get("created_by_importer", False)),
        destination_title=(
            str(note["destination_title"])
            if note.get("destination_title") is not None
            else None
        ),
        destination_updated_at=(
            str(note["destination_updated_at"])
            if note.get("destination_updated_at") is not None
            else None
        ),
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
    state: ImportState,
    note_id: str,
    status: str,
    error: str | None = None,
    destination_id: str | None = None,
    destination_folder: list[str] | None = None,
    session_id: str | None = None,
    created_by_importer: bool | None = None,
    destination_title: str | None = None,
    destination_updated_at: str | None = None,
) -> ImportState:
    notes = {
        existing_note_id: NoteState(
            status=existing_note.status,
            attempts=existing_note.attempts,
            fingerprint=existing_note.fingerprint,
            error=existing_note.error,
            destination_id=existing_note.destination_id,
            destination_folder=list(existing_note.destination_folder),
            session_id=existing_note.session_id,
            created_by_importer=existing_note.created_by_importer,
            destination_title=existing_note.destination_title,
            destination_updated_at=existing_note.destination_updated_at,
        )
        for existing_note_id, existing_note in state.notes.items()
    }
    note = notes.get(note_id, NoteState())
    note.status = status
    note.attempts += 1
    note.error = error
    if destination_id is not None:
        note.destination_id = destination_id
    if destination_folder is not None:
        note.destination_folder = list(destination_folder)
    if session_id is not None:
        note.session_id = session_id
    if created_by_importer is not None:
        note.created_by_importer = created_by_importer
    if destination_title is not None:
        note.destination_title = destination_title
    if destination_updated_at is not None:
        note.destination_updated_at = destination_updated_at
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
                "destination_id": note.destination_id,
                "destination_folder": note.destination_folder,
                "session_id": note.session_id,
                "created_by_importer": note.created_by_importer,
                "destination_title": note.destination_title,
                "destination_updated_at": note.destination_updated_at,
            }
        )
    return {"counts": counts, "notes": notes}
