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


@dataclass(frozen=True)
class ExportNoteRecord:
    source_id: int
    title: str
    notebook_path: list[str]
    tags: list[str]
    created_at: str
    updated_at: str
    html_path: Path
    raw_path: Path
    fingerprint: str
    provenance_marker: str


@dataclass(frozen=True)
class ExportManifest:
    notes: list[ExportNoteRecord]
    counts: dict[str, int]
