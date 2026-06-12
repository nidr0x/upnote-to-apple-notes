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


def run_jxa_import(script_path: Path, payload: dict[str, object]) -> dict[str, Any]:
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", str(script_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if not result.stdout.strip():
        return {"status": result.returncode, "notes": []}
    return json.loads(result.stdout)
