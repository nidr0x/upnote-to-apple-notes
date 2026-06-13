from __future__ import annotations

from pathlib import Path

from .models import SourceLocation

DATABASE_FILENAMES = ("UpNote.sqlite", "upnote.sqlite3")


class DiscoveryError(RuntimeError):
    def __init__(self, checked_locations: list[Path]):
        self.checked_locations = checked_locations
        checked = ", ".join(str(path) for path in checked_locations) or "<none>"
        super().__init__(f"Could not find UpNote.sqlite in: {checked}")


def discover_upnote_source(search_roots: list[Path]) -> SourceLocation:
    checked_locations: list[Path] = []

    for root in search_roots:
        checked_locations.append(root)
        for database_name in DATABASE_FILENAMES:
            database_path = root / database_name
            if database_path.is_file():
                assets_candidates = (root / "files", root / "images")
                assets_path = next(
                    (candidate for candidate in assets_candidates if candidate.exists()),
                    None,
                )
                return SourceLocation(
                    database_path=database_path,
                    assets_path=assets_path,
                    checked_locations=checked_locations,
                )

    raise DiscoveryError(checked_locations)


def discover_default_source() -> SourceLocation:
    return discover_upnote_source(
        [
            Path.home()
            / "Library"
            / "Containers"
            / "com.getupnote.desktop"
            / "Data"
            / "Library"
            / "Application Support"
            / "upnote",
            Path.home() / "Library" / "Application Support" / "UpNote",
            Path.home() / "Library" / "Containers",
        ]
    )
