from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from .apple_notes import build_jxa_payload, run_jxa_import
from .discovery import discover_default_source
from .extractor import SourceAccessError, extract_notes
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


def run_extract(export_root: Path, spaces_as_folders: bool = False) -> Path:
    source = discover_default_source()
    extraction = extract_notes(source.database_path)
    write_export_tree(
        extraction,
        export_root,
        source.database_path.parent,
        spaces_as_folders=spaces_as_folders,
    )
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
        workspace_name=(
            str(note["workspace_name"])
            if note.get("workspace_name") is not None
            else None
        ),
        note_links=[str(link) for link in note.get("note_links", [])],
        file_ids=[str(file_id) for file_id in note.get("file_ids", [])],
        pinned=bool(note.get("pinned", False)),
        bookmarked=bool(note.get("bookmarked", False)),
        is_template=bool(note.get("is_template", False)),
        rtl=bool(note.get("rtl", False)),
        attachment_paths=[Path(str(path)) for path in note.get("attachment_paths", [])],
    )


def run_import(
    export_root: Path,
    script_path: Path,
    state_path: Path,
    mode: str,
    account_name: str | None = None,
    batch_size: int = 50,
    session_id: str | None = None,
    source_ids: set[str] | None = None,
) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    manifest = load_manifest(export_root / "manifest.json")
    state = load_state(state_path)
    selected_notes = [
        note
        for note in manifest["notes"]
        if source_ids is None or str(note["source_id"]) in source_ids
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

    had_failures = False
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
        try:
            result = run_jxa_import(script_path, payload)
        except Exception as error:
            for note in batch:
                note_id = str(note["source_id"])
                state = mark_note_status(
                    state,
                    note_id,
                    "failed",
                    f"Apple Notes launcher failed: {error}",
                    session_id=session_id,
                )
                state.notes[note_id].fingerprint = str(note["fingerprint"])
            save_state(state_path, state)
            _write_latest_report(export_root, build_import_report(state))
            return 1
        results_by_id = {
            str(item.get("source_id")): item
            for item in result.get("notes", [])
            if isinstance(item, dict) and item.get("source_id") is not None
        }
        for note in batch:
            note_id = str(note["source_id"])
            outcome = results_by_id.get(note_id)
            if outcome is None:
                outcome = {
                    "status": "failed",
                    "error": "Apple Notes returned no result",
                }
            status = str(outcome.get("status", "failed"))
            if status not in {"created", "updated"}:
                status = "failed"
                had_failures = True
            error = str(outcome["error"]) if outcome.get("error") else None
            destination_id = (
                str(outcome["destination_id"])
                if outcome.get("destination_id") is not None
                else None
            )
            destination_title = (
                str(outcome["destination_title"])
                if outcome.get("destination_title") is not None
                else None
            )
            destination_updated_at = (
                str(outcome["destination_updated_at"])
                if outcome.get("destination_updated_at") is not None
                else None
            )
            folder_path = outcome.get("folder_path")
            destination_folder = (
                [str(part) for part in folder_path]
                if isinstance(folder_path, list)
                else None
            )
            state = mark_note_status(
                state,
                note_id,
                status,
                error,
                destination_id,
                destination_folder,
                session_id,
                True if status == "created" else None,
                destination_title,
                destination_updated_at,
            )
            state.notes[note_id].fingerprint = str(note["fingerprint"])
        save_state(state_path, state)
        _write_latest_report(export_root, build_import_report(state))
        completed = min(start + len(batch), len(selected_notes))
        print(f"Processed {completed} of {len(selected_notes)} notes")
    return 1 if had_failures else 0


def run_rollback(
    state_path: Path,
    script_path: Path,
    account_name: str | None,
    session_id: str,
    apply: bool,
) -> dict[str, object]:
    state = load_state(state_path)
    targets = [
        {
            "source_id": source_id,
            "destination_id": note.destination_id,
            "marker": f"upnote:{source_id}",
            "expected_title": note.destination_title,
            "expected_updated_at": note.destination_updated_at,
        }
        for source_id, note in state.notes.items()
        if note.session_id == session_id
        and note.created_by_importer
        and note.destination_id is not None
    ]
    if not apply:
        return {"session_id": session_id, "planned": len(targets), "deleted": 0}
    result = run_jxa_import(
        script_path,
        {
            "operation": "rollback",
            "account_name": account_name,
            "notes": targets,
        },
    )
    outcomes = result.get("notes", [])
    deleted_ids = {
        str(outcome["source_id"])
        for outcome in outcomes
        if isinstance(outcome, dict) and outcome.get("status") == "deleted"
    }
    for source_id in deleted_ids:
        state = mark_note_status(state, source_id, "rolled-back")
    save_state(state_path, state)
    return {
        "session_id": session_id,
        "planned": len(targets),
        "deleted": len(deleted_ids),
        "failed": len(targets) - len(deleted_ids),
    }


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
        "capabilities": {
            "workspaces": {
                "detected": int(manifest.get("counts", {}).get("workspaces", 0)),
                "mapping": (
                    "top-level-folders"
                    if manifest.get("options", {}).get("spaces_as_folders")
                    else "metadata-only"
                ),
            },
            "internal_links": {
                "detected": sum(
                    len(note.get("note_links", []))
                    for note in notes
                    if isinstance(note, dict)
                ),
                "mapping": "ledger-preserved",
            },
            "file_links": {
                "detected": sum(
                    len(note.get("file_ids", []))
                    for note in notes
                    if isinstance(note, dict)
                ),
                "mapping": "asset-copy",
            },
            "unsupported_metadata": {
                field: sum(
                    bool(note.get(field)) for note in notes if isinstance(note, dict)
                )
                for field in ("pinned", "bookmarked", "is_template", "rtl")
            },
        },
    }


def run_verify(
    export_root: Path,
    script_path: Path,
    account_name: str | None,
    source_ids: set[str] | None = None,
) -> dict[str, object]:
    manifest = load_manifest(export_root / "manifest.json")
    notes = manifest.get("notes", [])
    markers = [
        str(note["provenance_marker"])
        for note in notes
        if isinstance(note, dict)
        and (source_ids is None or str(note["source_id"]) in source_ids)
    ]
    result = run_jxa_import(
        script_path,
        {"operation": "verify", "account_name": account_name, "markers": markers},
    )
    found = result.get("notes", {})
    if not isinstance(found, dict):
        found = {}
    missing: list[str] = []
    duplicates: list[str] = []
    mismatched: list[dict[str, object]] = []
    matched = 0
    for note in notes:
        if not isinstance(note, dict):
            continue
        source_id = str(note["source_id"])
        if source_ids is not None and source_id not in source_ids:
            continue
        marker = str(note["provenance_marker"])
        destinations = found.get(marker, [])
        if not isinstance(destinations, list) or not destinations:
            missing.append(source_id)
            continue
        if len(destinations) > 1:
            duplicates.append(source_id)
            continue
        destination = destinations[0]
        if not isinstance(destination, dict):
            mismatched.append({"source_id": source_id, "reasons": ["invalid-result"]})
            continue
        reasons = _verification_reasons(export_root, note, destination)
        if reasons:
            mismatched.append({"source_id": source_id, "reasons": reasons})
        else:
            matched += 1
    return {
        "expected": len(markers),
        "matched": matched,
        "missing": missing,
        "duplicates": duplicates,
        "mismatched": mismatched,
        "ready": not missing and not duplicates and not mismatched,
    }


class _HtmlText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _html_text(value: str) -> str:
    parser = _HtmlText()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())


def _date_timestamp(value: object) -> int | None:
    try:
        if isinstance(value, (int, float)) or re.fullmatch(r"-?\d+(?:\.\d+)?", str(value)):
            number = float(value)
            return round(number / 1000 if abs(number) >= 100_000_000_000 else number)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return round(parsed.timestamp())
    except (TypeError, ValueError, OverflowError):
        return None


def _normalized_tags(tags: object) -> list[str]:
    if not isinstance(tags, list):
        return []
    return [
        f"#{re.sub(r'\s+', '-', str(tag).strip().lstrip('#'))}"
        for tag in tags
        if str(tag).strip().lstrip("#")
    ]


def _verification_reasons(
    export_root: Path, source: dict[str, object], destination: dict[str, object]
) -> list[str]:
    reasons: list[str] = []
    if str(destination.get("title", "")) != str(source.get("title", "")):
        reasons.append("title")
    if list(destination.get("folder_path", [])) != list(source.get("notebook_path", [])):
        reasons.append("folder")

    destination_body = str(destination.get("body", ""))
    source_body = (export_root / str(source["html_path"])).read_text(encoding="utf-8")
    source_text = _html_text(source_body)
    destination_text = _html_text(destination_body)
    if source_text and not destination_text.startswith(source_text):
        reasons.append("body")
    if any(tag not in destination_text for tag in _normalized_tags(source.get("tags"))):
        reasons.append("tags")
    if f"UpNote source: {source['provenance_marker']}" not in destination_text:
        reasons.append("provenance")
    expected_attachments = {
        Path(str(path)).name for path in source.get("attachment_paths", [])
    }
    destination_attachments = {
        str(name) for name in destination.get("attachment_names", [])
    }
    if expected_attachments != destination_attachments:
        reasons.append("attachments")
    if _date_timestamp(destination.get("created_at")) != _date_timestamp(source.get("created_at")):
        reasons.append("created-at")
    if _date_timestamp(destination.get("updated_at")) != _date_timestamp(source.get("updated_at")):
        reasons.append("updated-at")
    return reasons


def cmd_discover(_args: argparse.Namespace) -> int:
    source = discover_default_source()
    print(source.database_path)
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    try:
        run_extract(args.export_root, args.spaces_as_folders)
    except SourceAccessError as error:
        print(str(error), file=sys.stderr)
        return 1
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
    report = run_preflight(args.export_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 1


def cmd_accounts(_args: argparse.Namespace) -> int:
    result = run_jxa_import(_script_path(), {"operation": "accounts"})
    print(json.dumps(result["accounts"], indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    report = run_verify(args.export_root, _script_path(), args.account)
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 1


def cmd_migrate(args: argparse.Namespace) -> int:
    session_id = str(uuid.uuid4())
    try:
        run_extract(args.export_root, args.spaces_as_folders)
    except SourceAccessError as error:
        print(str(error), file=sys.stderr)
        return 1
    preflight = run_preflight(args.export_root)
    print(json.dumps(preflight, indent=2, sort_keys=True))
    if not preflight["ready"]:
        return 1
    manifest = load_manifest(args.export_root / "manifest.json")
    all_source_ids = {
        str(note["source_id"]) for note in manifest["notes"]
    }
    canary_ids = (
        {str(note["source_id"]) for note in manifest["notes"][: args.canary]}
        if args.canary
        else None
    )
    result = run_import(
        args.export_root,
        _script_path(),
        args.export_root / "state" / "import-state.json",
        "skip-existing",
        args.account,
        args.batch_size,
        session_id,
        canary_ids,
    )
    if result != 0:
        return result
    if canary_ids is not None:
        canary_verification = run_verify(
            args.export_root, _script_path(), args.account, canary_ids
        )
        print(json.dumps({"canary": canary_verification}, indent=2))
        if not canary_verification["ready"]:
            return 1
        result = run_import(
            args.export_root,
            _script_path(),
            args.export_root / "state" / "import-state.json",
            "resume",
            args.account,
            args.batch_size,
            session_id,
            all_source_ids,
        )
        if result != 0:
            return result
    verification = run_verify(args.export_root, _script_path(), args.account)
    print(json.dumps(verification, indent=2))
    return 0 if verification["ready"] else 1


def cmd_rollback(args: argparse.Namespace) -> int:
    report = run_rollback(
        args.export_root / "state" / "import-state.json",
        _script_path(),
        args.account,
        args.session_id,
        args.apply,
    )
    print(json.dumps(report, indent=2))
    return 0 if not args.apply or report.get("failed") == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upnote-to-apple-notes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover")
    discover_parser.set_defaults(func=cmd_discover)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("--export-root", type=Path, required=True)
    extract_parser.add_argument(
        "--spaces-as-folders",
        action="store_true",
        help="Prefix notebook paths with their UpNote Space name",
    )
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

    migrate_parser = subparsers.add_parser("migrate")
    migrate_parser.add_argument("--export-root", type=Path, required=True)
    migrate_parser.add_argument("--account", help="Exact Apple Notes account name")
    migrate_parser.add_argument("--batch-size", type=_positive_integer, default=50)
    migrate_parser.add_argument(
        "--canary",
        type=_positive_integer,
        help="Validate this many notes before importing the remainder",
    )
    migrate_parser.add_argument("--spaces-as-folders", action="store_true")
    migrate_parser.set_defaults(func=cmd_migrate)

    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("--export-root", type=Path, required=True)
    rollback_parser.add_argument("--account", help="Exact Apple Notes account name")
    rollback_parser.add_argument("--session-id", required=True)
    rollback_parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete notes created by this migration session",
    )
    rollback_parser.set_defaults(func=cmd_rollback)

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
