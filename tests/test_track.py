import json
import os
import shutil
from types import SimpleNamespace

import pytest
from util import arun

import streamrip.db as db
from streamrip.client.downloadable import Downloadable
from streamrip.client.qobuz import QobuzClient
from streamrip.config import Config
from streamrip.media.track import PendingSingle, Track
from streamrip.metadata import AlbumMetadata

with open("tests/qobuz_album_resp.json") as f:
    _album_resp = json.load(f)


def test_pending_single_format_folder_honors_source_and_restrict():
    """PendingSingle._format_folder routes through AlbumMetadata.build_folder_path,
    so it honors source_subdirectories and restrict_characters (previously skipped)."""
    album = AlbumMetadata.from_qobuz(_album_resp)  # "Rumours"
    config = Config("tests/test_config.toml")
    config.session.downloads.source_subdirectories = True
    config.session.filepaths.folder_format = "{albumtitle}"
    config.session.filepaths.restrict_characters = True

    p = PendingSingle(
        "1",
        SimpleNamespace(source="qobuz"),
        config,
        None,  # type: ignore[arg-type]  # db unused by _format_folder
    )
    expected = os.path.join(config.session.downloads.folder, "Qobuz", "Rumours")
    assert p._format_folder(album) == expected


@pytest.mark.skipif(
    "QOBUZ_EMAIL" not in os.environ, reason="Qobuz credentials not found in env."
)
def test_pending_resolve(qobuz_client: QobuzClient):
    qobuz_client.config.session.downloads.folder = "./tests"
    p = PendingSingle(
        "19512574",
        qobuz_client,
        qobuz_client.config,
        db.Database(db.Dummy(), db.Dummy()),
    )
    t = arun(p.resolve())
    dir = "tests/tests/Fleetwood Mac - Rumours (1977) [FLAC] [24B-96kHz]"
    assert os.path.isdir(dir)
    assert os.path.isfile(os.path.join(dir, "cover.jpg"))
    assert os.path.isfile(t.cover_path)
    assert isinstance(t, Track)
    assert isinstance(t.downloadable, Downloadable)
    assert t.cover_path is not None
    shutil.rmtree(dir)
