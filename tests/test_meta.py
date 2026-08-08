import json
import os

from streamrip.metadata import AlbumMetadata, TrackMetadata

with open("tests/qobuz_album_resp.json") as f:
    qobuz_album_resp = json.load(f)

with open("tests/qobuz_track_resp.json") as f:
    qobuz_track_resp = json.load(f)


def test_album_metadata_qobuz():
    m = AlbumMetadata.from_qobuz(qobuz_album_resp)
    info = m.info
    assert info.id == "19512572"
    assert info.quality == 3
    assert info.container == "FLAC"
    assert info.label == "Rhino - Warner Records"
    assert info.explicit is False
    assert info.sampling_rate == 96
    assert info.bit_depth == 24
    assert info.booklets is None

    assert m.album == "Rumours"
    assert m.albumartist == "Fleetwood Mac"
    assert m.year == "1977"
    assert "Rock" in m.genre
    assert not m.covers.empty()

    assert m.albumcomposer == "Various Composers"
    assert m.comment is None
    assert m.compilation is None
    assert (
        m.copyright
        == "© 1977 Warner Records Inc. ℗ 1977 Warner Records Inc. Marketed by Rhino Entertainment Company, A Warner Music Group Company."
    )
    assert m.date == "1977-02-04"
    assert m.description == ""
    assert m.disctotal == 1
    assert m.encoder is None
    assert m.grouping is None
    assert m.lyrics is None
    assert m.purchase_date is None
    assert m.tracktotal == 11


def test_track_metadata_qobuz():
    a = AlbumMetadata.from_qobuz(qobuz_track_resp["album"])
    t = TrackMetadata.from_qobuz(a, qobuz_track_resp)
    info = t.info
    assert info.id == "216020864"
    assert info.quality == 3
    assert info.bit_depth == 24
    assert info.sampling_rate == 96
    assert info.work is None

    assert t.title == "Water Tower"
    assert t.album == a
    assert t.artist == "The Mountain Goats"
    assert t.tracknumber == 9
    assert t.discnumber == 1
    assert t.composer == "John Darnielle"


def test_album_folder_path_title_keys():
    m = AlbumMetadata.from_qobuz(qobuz_album_resp)
    # new explicit keys render the album title
    assert m.format_folder_path("{albumtitle}") == "Rumours"
    assert m.format_folder_path("{album_title}") == "Rumours"
    # backward compat: title still resolves to the album title in folder context
    assert m.format_folder_path("{title}") == "Rumours"


def test_track_path_title_keys():
    a = AlbumMetadata.from_qobuz(qobuz_track_resp["album"])
    t = TrackMetadata.from_qobuz(a, qobuz_track_resp)
    # new explicit track-title keys
    assert t.format_track_path("{tracktitle}") == "Water Tower"
    assert t.format_track_path("{track_title}") == "Water Tower"
    # track context also exposes the album title
    assert t.format_track_path("{albumtitle}") == "Jenny from Thebes"
    assert t.format_track_path("{album_title}") == "Jenny from Thebes"
    # backward compat: title still resolves to the track title in track context
    assert t.format_track_path("{title}") == "Water Tower"


def test_build_folder_path():
    m = AlbumMetadata.from_qobuz(qobuz_album_resp)  # "Rumours", 1977
    # parent + rendered album folder
    assert m.build_folder_path("PARENT", "{albumtitle}") == os.path.join(
        "PARENT", "Rumours"
    )
    # source_subdirectories prepends a capitalized source folder
    assert m.build_folder_path(
        "PARENT", "{albumtitle}", source_subdirectories=True, source="qobuz"
    ) == os.path.join("PARENT", "Qobuz", "Rumours")
    # restrict_characters is applied (ASCII content is unchanged)
    assert m.build_folder_path("PARENT", "{albumtitle}", restrict=True) == os.path.join(
        "PARENT", "Rumours"
    )
    # a leading separator in the rendered path cannot escape the parent
    assert m.build_folder_path("PARENT", "/{albumtitle}") == os.path.join(
        "PARENT", "Rumours"
    )
