from __future__ import annotations

from pathlib import Path

from .models import SourceLocation


class DiscoveryError(RuntimeError):
    def __init__(self, checked_locations: list[Path]):
        self.checked_locations = checked_locations
        checked = ", ".join(str(path) for path in checked_locations) or "<none>"
        super().__init__(f"Could not find UpNote.sqlite in: {checked}")


def discover_upnote_source(search_roots: list[Path]) -> SourceLocation:
    checked_locations: list[Path] = []

    for root in search_roots:
        checked_locations.append(root)
        database_path = root / "UpNote.sqlite"
        if database_path.exists():
            assets_path = root / "files"
            return SourceLocation(
                database_path=database_path,
                assets_path=assets_path if assets_path.exists() else None,
                checked_locations=checked_locations,
            )

    raise DiscoveryError(checked_locations)


def discover_default_source() -> SourceLocation:
    return discover_upnote_source(
        [
            Path.home() / "Library" / "Application Support" / "UpNote",
            Path.home() / "Library" / "Containers",
        ]
    )
