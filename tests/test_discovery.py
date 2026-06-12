from pathlib import Path

import pytest

from upnote_to_apple_notes.discovery import DiscoveryError, discover_upnote_source


def test_discover_upnote_source_returns_database_and_assets(tmp_path: Path):
    db_path = tmp_path / "UpNote.sqlite"
    db_path.write_text("")
    assets_path = tmp_path / "files"
    assets_path.mkdir()

    result = discover_upnote_source([tmp_path])

    assert result.database_path == db_path
    assert result.assets_path == assets_path
    assert result.checked_locations == [tmp_path]


def test_discover_upnote_source_reports_checked_locations(tmp_path: Path):
    with pytest.raises(DiscoveryError) as exc:
        discover_upnote_source([tmp_path])

    assert exc.value.checked_locations == [tmp_path]
    assert "UpNote.sqlite" in str(exc.value)
