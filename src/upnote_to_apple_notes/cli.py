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
    write_export_tree(extraction, export_root, source.database_path.parent)
    return export_root


def _manifest_note_to_export_note(note: dict[str, object]) -> ExportNoteRecord:
    return ExportNoteRecord(
        source_id=str(note["source_id"]),
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


def run_import(
    export_root: Path,
    script_path: Path,
    state_path: Path,
    mode: str,
    account_name: str | None = None,
    batch_size: int = 50,
) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
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

    for start in range(0, len(selected_notes), batch_size):
        batch = selected_notes[start : start + batch_size]
        payload = build_jxa_payload(
            ExportManifest(
                notes=[_manifest_note_to_export_note(note) for note in batch],
                counts={"notes": len(batch)},
            ),
            export_root,
            account_name,
        )
        result = run_jxa_import(script_path, payload)
        results_by_id = {
            str(item.get("source_id")): item
            for item in result.get("notes", [])
            if isinstance(item, dict) and item.get("source_id") is not None
        }
        for note in batch:
            note_id = str(note["source_id"])
            outcome = results_by_id.get(note_id)
            if outcome is None:
                continue
            status = str(outcome.get("status", "failed"))
            error = str(outcome["error"]) if outcome.get("error") else None
            state = mark_note_status(state, note_id, status, error)
            state.notes[note_id].fingerprint = str(note["fingerprint"])
        save_state(state_path, state)
        _write_latest_report(export_root, build_import_report(state))
    return 0


def _script_path() -> Path:
    return Path(__file__).with_name("jxa").joinpath("import_notes.js")


def run_preflight(export_root: Path) -> dict[str, object]:
    manifest = load_manifest(export_root / "manifest.json")
    notes = manifest.get("notes", [])
    if not isinstance(notes, list):
        raise ValueError("Manifest notes must be a list")
    missing_html = [
        str(note.get("source_id"))
        for note in notes
        if isinstance(note, dict) and not (export_root / str(note["html_path"])).is_file()
    ]
    tags = {
        tag
        for note in notes
        if isinstance(note, dict)
        for tag in note.get("tags", [])
    }
    assets = manifest.get("assets", {})
    if not isinstance(assets, dict):
        assets = {}
    missing_assets = assets.get("missing_references", [])
    if not isinstance(missing_assets, list):
        missing_assets = []
    return {
        "notes": len(notes),
        "notebooks": manifest.get("counts", {}).get("notebooks", 0),
        "unique_tags": len(tags),
        "copied_assets": assets.get("copied_files", 0),
        "missing_html": missing_html,
        "missing_assets": missing_assets,
        "ready": not missing_html and not missing_assets,
    }


def run_verify(export_root: Path, script_path: Path, account_name: str | None) -> dict[str, object]:
    manifest = load_manifest(export_root / "manifest.json")
    notes = manifest.get("notes", [])
    markers = [str(note["provenance_marker"]) for note in notes if isinstance(note, dict)]
    result = run_jxa_import(
        script_path,
        {"operation": "verify", "account_name": account_name, "markers": markers},
    )
    found = result.get("markers", {})
    if not isinstance(found, dict):
        found = {}
    missing = [marker for marker in markers if not found.get(marker)]
    return {"expected": len(markers), "found": len(markers) - len(missing), "missing": missing}


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
        script_path=_script_path(),
        state_path=args.export_root / "state" / "import-state.json",
        mode=args.mode,
        account_name=args.account,
        batch_size=args.batch_size,
    )


def cmd_resume(args: argparse.Namespace) -> int:
    return run_import(
        export_root=args.export_root,
        script_path=_script_path(),
        state_path=args.export_root / "state" / "import-state.json",
        mode="resume",
        account_name=args.account,
        batch_size=args.batch_size,
    )


def cmd_report(args: argparse.Namespace) -> int:
    print(
        (args.export_root / "reports" / "latest-report.json").read_text(encoding="utf-8")
    )
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    print(json.dumps(run_preflight(args.export_root), indent=2, sort_keys=True))
    return 0


def cmd_accounts(_args: argparse.Namespace) -> int:
    result = run_jxa_import(_script_path(), {"operation": "accounts"})
    print(json.dumps(result["accounts"], indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    print(json.dumps(run_verify(args.export_root, _script_path(), args.account), indent=2))
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
    import_parser.add_argument("--account", help="Exact Apple Notes account name")
    import_parser.add_argument("--batch-size", type=_positive_integer, default=50)
    import_parser.set_defaults(func=cmd_import)

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--export-root", type=Path, required=True)
    resume_parser.add_argument("--account", help="Exact Apple Notes account name")
    resume_parser.add_argument("--batch-size", type=_positive_integer, default=50)
    resume_parser.set_defaults(func=cmd_resume)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--export-root", type=Path, required=True)
    report_parser.set_defaults(func=cmd_report)

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--export-root", type=Path, required=True)
    preflight_parser.set_defaults(func=cmd_preflight)

    accounts_parser = subparsers.add_parser("accounts")
    accounts_parser.set_defaults(func=cmd_accounts)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--export-root", type=Path, required=True)
    verify_parser.add_argument("--account", help="Exact Apple Notes account name")
    verify_parser.set_defaults(func=cmd_verify)

    return parser


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main() -> int:
    args = build_parser().parse_args()
    handler = getattr(args, "func", None)
    if handler is not None:
        return handler(args)
    return 0
