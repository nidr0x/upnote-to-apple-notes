from __future__ import annotations

import argparse
import json
from pathlib import Path

from .apple_notes import build_jxa_payload, run_jxa_import
from .discovery import discover_default_source
from .extractor import extract_notes
from .models import ExportManifest, ExportNoteRecord
from .normalize import load_manifest, write_export_tree
from .state import (
    build_import_report,
    load_state,
    mark_note_status,
    save_state,
    should_import_note,
)


def _write_latest_report(export_root: Path, report: dict[str, object]) -> None:
    reports_dir = export_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "latest-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def run_extract(export_root: Path) -> Path:
    source = discover_default_source()
    extraction = extract_notes(source.database_path)
    write_export_tree(extraction, export_root)
    return export_root


def _manifest_note_to_export_note(note: dict[str, object]) -> ExportNoteRecord:
    return ExportNoteRecord(
        source_id=int(note["source_id"]),
        title=str(note["title"]),
        notebook_path=list(note["notebook_path"]),
        tags=list(note["tags"]),
        created_at=str(note["created_at"]),
        updated_at=str(note["updated_at"]),
        html_path=Path(str(note["html_path"])),
        raw_path=Path(str(note["raw_path"])),
        fingerprint=str(note["fingerprint"]),
        provenance_marker=str(note["provenance_marker"]),
    )


def _imported_note_ids(result: dict[str, object]) -> set[str]:
    notes = result.get("notes", [])
    if not isinstance(notes, list):
        return set()

    imported_ids: set[str] = set()
    for note in notes:
        if not isinstance(note, dict):
            continue
        source_id = note.get("source_id")
        if source_id is None:
            continue
        imported_ids.add(str(source_id))
    return imported_ids


def run_import(
    export_root: Path, script_path: Path, state_path: Path, mode: str
) -> int:
    manifest = load_manifest(export_root / "manifest.json")
    state = load_state(state_path)
    selected_notes = [
        note
        for note in manifest["notes"]
        if should_import_note(
            state,
            str(note["source_id"]),
            str(note["fingerprint"]),
            mode,
        )
    ]

    if mode == "dry-run":
        for note in selected_notes:
            note_id = str(note["source_id"])
            state = mark_note_status(state, note_id, "planned")
            state.notes[note_id].fingerprint = str(note["fingerprint"])
        save_state(state_path, state)
        report = build_import_report(state)
        _write_latest_report(export_root, report)
        return 0

    payload = build_jxa_payload(
        ExportManifest(
            notes=[_manifest_note_to_export_note(note) for note in selected_notes],
            counts={"notes": len(selected_notes)},
        ),
        export_root,
    )
    result = run_jxa_import(script_path, payload)
    imported_ids = _imported_note_ids(result)

    for note in selected_notes:
        note_id = str(note["source_id"])
        if note_id not in imported_ids:
            continue
        state = mark_note_status(state, note_id, "created")
        state.notes[note_id].fingerprint = str(note["fingerprint"])

    save_state(state_path, state)
    report = build_import_report(state)
    _write_latest_report(export_root, report)
    return int(result.get("returncode", 0))


def cmd_discover(_args: argparse.Namespace) -> int:
    source = discover_default_source()
    print(source.database_path)
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    run_extract(args.export_root)
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    return run_import(
        export_root=args.export_root,
        script_path=Path(__file__).with_name("jxa").joinpath("import_notes.js"),
        state_path=args.export_root / "state" / "import-state.json",
        mode=args.mode,
    )


def cmd_resume(args: argparse.Namespace) -> int:
    return run_import(
        export_root=args.export_root,
        script_path=Path(__file__).with_name("jxa").joinpath("import_notes.js"),
        state_path=args.export_root / "state" / "import-state.json",
        mode="resume",
    )


def cmd_report(args: argparse.Namespace) -> int:
    print(
        (args.export_root / "reports" / "latest-report.json").read_text(encoding="utf-8")
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upnote-to-apple-notes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover")
    discover_parser.set_defaults(func=cmd_discover)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("--export-root", type=Path, required=True)
    extract_parser.set_defaults(func=cmd_extract)

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--export-root", type=Path, required=True)
    import_parser.add_argument(
        "--mode",
        choices=["dry-run", "skip-existing", "update-changed"],
        default="dry-run",
    )
    import_parser.set_defaults(func=cmd_import)

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--export-root", type=Path, required=True)
    resume_parser.set_defaults(func=cmd_resume)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--export-root", type=Path, required=True)
    report_parser.set_defaults(func=cmd_report)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    handler = getattr(args, "func", None)
    if handler is not None:
        return handler(args)
    return 0
