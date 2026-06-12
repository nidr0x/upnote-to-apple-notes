from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceLocation:
    database_path: Path
    assets_path: Path | None
    checked_locations: list[Path]
