import os

from streamrip.config import Config
from streamrip.media.album import rename_to_match_quality
from streamrip.metadata import AlbumInfo, AlbumMetadata, Covers

FMT = "{albumartist} - {title} ({year}) [{bit_depth}B-{sampling_rate}kHz]"


def _meta(sampling_rate, bit_depth):
    return AlbumMetadata(
        AlbumInfo(
            id="1",
            quality=4,
            container="FLAC",
            sampling_rate=sampling_rate,
            bit_depth=bit_depth,
        ),
        album="Album",
        albumartist="Artist",
        year="2020",
        genre=[],
        covers=Covers(),
        tracktotal=10,
    )


def _cfg():
    cfg = Config.defaults().session.filepaths
    cfg.folder_format = FMT
    cfg.restrict_characters = False
    return cfg


def test_folder_renamed_when_delivered_quality_differs(tmp_path):
    # Pre-download placeholder (Tidal HiRes quality-4 album): 16/44.1.
    meta = _meta(sampling_rate=44100, bit_depth=16)
    cfg = _cfg()
    placeholder = os.path.join(tmp_path, meta.format_folder_path(cfg.folder_format))
    os.makedirs(placeholder)
    sentinel = os.path.join(placeholder, "track.flac")
    open(sentinel, "w").close()

    # postprocess corrects album.info to the delivered stream (24/48).
    meta.info.sampling_rate = 48000
    meta.info.bit_depth = 24

    result = rename_to_match_quality(placeholder, meta, cfg)

    assert result != placeholder
    assert not os.path.exists(placeholder)  # old folder gone
    assert os.path.isdir(result)  # new folder exists
    assert os.path.exists(os.path.join(result, "track.flac"))  # contents moved
    assert "24B-48000kHz" in os.path.basename(result)


def test_folder_not_renamed_when_delivered_matches_placeholder(tmp_path):
    meta = _meta(sampling_rate=44100, bit_depth=16)
    cfg = _cfg()
    folder = os.path.join(tmp_path, meta.format_folder_path(cfg.folder_format))
    os.makedirs(folder)

    # Delivered quality matches the placeholder -> no rename.
    result = rename_to_match_quality(folder, meta, cfg)
    assert result == folder
    assert os.path.isdir(folder)


def test_folder_not_renamed_when_target_exists(tmp_path):
    meta = _meta(sampling_rate=44100, bit_depth=16)
    cfg = _cfg()
    placeholder = os.path.join(tmp_path, meta.format_folder_path(cfg.folder_format))
    os.makedirs(placeholder)

    meta.info.sampling_rate = 48000
    meta.info.bit_depth = 24
    # Pre-create the target so the rename must be skipped, not clobbered.
    os.makedirs(os.path.join(tmp_path, meta.format_folder_path(cfg.folder_format)))

    result = rename_to_match_quality(placeholder, meta, cfg)
    assert result == placeholder  # unchanged
    assert os.path.isdir(placeholder)  # original preserved
