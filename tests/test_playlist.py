import json
import os

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
