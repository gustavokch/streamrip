import json
import os
import types

import pytest

from streamrip.config import Config
from streamrip.media.playlist import PendingPlaylistTrack
from streamrip.metadata import AlbumMetadata

FIXTURE = "tests/qobuz_track_resp.json"
SAMPLE_CONFIG = "tests/test_config.toml"


def _album() -> AlbumMetadata:
    with open(FIXTURE) as f:
        resp = json.load(f)
    album = AlbumMetadata.from_track_resp(resp, "qobuz")
    assert album is not None
    return album


def _pending(config: Config) -> PendingPlaylistTrack:
    # `client` and `db` are unused by `_track_folder`.
    return PendingPlaylistTrack(
        id="1",
        client=None,  # type: ignore[arg-type]
        config=config,
        folder="PL",
        playlist_name="x",
        position=1,
        db=None,  # type: ignore[arg-type]
    )


def test_track_folder_flat_when_disabled():
    config = Config(SAMPLE_CONFIG)
    config.session.metadata.dj_playlist = False

    assert _pending(config)._track_folder(_album()) == "PL"


def test_track_folder_nested_when_enabled():
    config = Config(SAMPLE_CONFIG)
    config.session.metadata.dj_playlist = True
    config.session.filepaths.dj_folder_format = "{albumartist}/{title} - {year}"

    expected = os.path.join("PL", "The Mountain Goats", "Jenny from Thebes - 2023")
    assert _pending(config)._track_folder(_album()) == expected


def test_track_folder_honors_source_subdirectories():
    config = Config(SAMPLE_CONFIG)
    config.session.metadata.dj_playlist = True
    config.session.downloads.source_subdirectories = True
    config.session.filepaths.dj_folder_format = "{albumtitle}"
    pending = PendingPlaylistTrack(
        id="1",
        client=types.SimpleNamespace(source="qobuz"),
        config=config,
        folder="PL",
        playlist_name="x",
        position=1,
        db=None,  # type: ignore[arg-type]
    )
    expected = os.path.join("PL", "Qobuz", "Jenny from Thebes")
    assert pending._track_folder(_album()) == expected


@pytest.mark.asyncio
async def test_download_cover_for_playlist_flag_follows_dj(monkeypatch):
    captured = {}

    async def fake_download_artwork(session, folder, covers, artwork, for_playlist):
        captured["for_playlist"] = for_playlist
        return (None, None)

    monkeypatch.setattr(
        "streamrip.media.playlist.download_artwork", fake_download_artwork
    )

    def pending(dj: bool) -> PendingPlaylistTrack:
        config = Config(SAMPLE_CONFIG)
        config.session.metadata.dj_playlist = dj
        return PendingPlaylistTrack(
            id="1",
            client=types.SimpleNamespace(session=None),
            config=config,
            folder="PL",
            playlist_name="x",
            position=1,
            db=None,  # type: ignore[arg-type]
        )

    # dj on -> honor save_artwork (as an album rip): for_playlist False
    await pending(True)._download_cover(None, "PL")
    assert captured["for_playlist"] is False

    # dj off -> flat playlist: no saved cover, for_playlist True
    await pending(False)._download_cover(None, "PL")
    assert captured["for_playlist"] is True
