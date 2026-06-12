from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SourceLocation:
    database_path: Path
    assets_path: Path | None
    checked_locations: list[Path]


@dataclass(frozen=True)
class NotebookRecord:
    source_id: int
    name: str


@dataclass(frozen=True)
class NoteRecord:
    source_id: int
    notebook_id: int
    title: str
    raw_content: str
    created_at: str
    updated_at: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractionResult:
    notebooks: list[NotebookRecord]
    notes: list[NoteRecord]
