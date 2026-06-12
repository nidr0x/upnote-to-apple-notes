from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .models import ExportManifest


def build_jxa_payload(manifest: ExportManifest, export_root: Path) -> dict[str, object]:
    return {
        "notes": [
            {
                "source_id": note.source_id,
                "title": note.title,
                "folder": note.notebook_path,
                "html_path": str(export_root / note.html_path),
                "marker": note.provenance_marker,
            }
            for note in manifest.notes
        ]
    }


def _serialize_jxa_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload)


def run_jxa_import(script_path: Path, payload: dict[str, object]) -> dict[str, Any]:
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", str(script_path)],
        input=_serialize_jxa_payload(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "JXA import failed"
        raise RuntimeError(
            f"JXA import failed with exit code {result.returncode}: {message}"
        )
    if not result.stdout.strip():
        raise RuntimeError("JXA import returned no output")
    payload = json.loads(result.stdout)
    payload.setdefault("returncode", result.returncode)
    return payload
