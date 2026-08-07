import base64
import json
from unittest.mock import Mock

import pytest
from util import arun

from streamrip.client.downloadable import TidalDownloadable
from streamrip.client.tidal import TidalClient
from streamrip.config import Config
from streamrip.exceptions import NonStreamableError
from streamrip.metadata import AlbumMetadata, TrackMetadata


def _manifest(codecs="flac", sample_rate=44100, bit_depth=16, url="https://x"):
    """A decoded Tidal playback manifest."""
    return {
        "codecs": codecs,
        "sampleRate": sample_rate,
        "bitsPerSample": bit_depth,
        "urls": [url],
        "encryptionType": "NONE",
    }


def _resp(manifest_dict):
    """A playbackinfopostpaywall response wrapping a manifest."""
    return {"manifest": base64.b64encode(json.dumps(manifest_dict).encode()).decode()}


def _client(responses):
    """Build a TidalClient whose _api_request returns per-quality responses.

    ``responses`` maps an ``audioquality`` string to the response dict that
    ``playbackinfopostpaywall`` should return for it. Missing qualities return
    ``{}`` (no manifest). ``client.requested`` records the quality of each call
    in order.
    """
    config = Config.defaults()
    client = TidalClient(config)
    client.session = Mock()
    requested = []

    async def fake_api_request(path, params=None, base=None):
        quality = params["audioquality"]
        requested.append(quality)
        return responses.get(quality, {})

    client._api_request = fake_api_request
    client.requested = requested
    return client


# ===== get_downloadable: quality 4 cap + fallback =====


def test_quality4_accepts_44100_16():
    client = _client(
        {"HI_RES_LOSSLESS": _resp(_manifest(sample_rate=44100, bit_depth=16))}
    )
    dl = arun(client.get_downloadable("1", 4))
    assert isinstance(dl, TidalDownloadable)
    assert dl.extension == "flac"
    assert dl.sampling_rate == 44100
    assert dl.bit_depth == 16
    assert client.requested == ["HI_RES_LOSSLESS"]


def test_quality4_rejects_96000_falls_back_to_lossless():
    client = _client(
        {
            "HI_RES_LOSSLESS": _resp(_manifest(sample_rate=96000, bit_depth=24)),
            "LOSSLESS": _resp(_manifest(sample_rate=44100, bit_depth=16)),
        }
    )
    dl = arun(client.get_downloadable("1", 4))
    assert dl.sampling_rate == 44100
    assert dl.bit_depth == 16
    assert client.requested == ["HI_RES_LOSSLESS", "LOSSLESS"]
    assert "HI_RES" not in client.requested  # never falls back to MQA


def test_quality4_boundary_48000_24_accepted():
    client = _client(
        {"HI_RES_LOSSLESS": _resp(_manifest(sample_rate=48000, bit_depth=24))}
    )
    dl = arun(client.get_downloadable("1", 4))
    assert dl.sampling_rate == 48000
    assert dl.bit_depth == 24
    assert client.requested == ["HI_RES_LOSSLESS"]


def test_quality4_boundary_88200_rejected():
    client = _client(
        {
            "HI_RES_LOSSLESS": _resp(_manifest(sample_rate=88200, bit_depth=24)),
            "LOSSLESS": _resp(_manifest(sample_rate=44100, bit_depth=16)),
        }
    )
    arun(client.get_downloadable("1", 4))
    assert client.requested == ["HI_RES_LOSSLESS", "LOSSLESS"]


def test_quality4_missing_manifest_falls_back_not_mqa():
    client = _client(
        {
            "HI_RES_LOSSLESS": {},  # no manifest key
            "LOSSLESS": _resp(_manifest(sample_rate=44100, bit_depth=16)),
        }
    )
    dl = arun(client.get_downloadable("1", 4))
    assert dl.sampling_rate == 44100
    assert client.requested == ["HI_RES_LOSSLESS", "LOSSLESS"]
    assert "HI_RES" not in client.requested


def test_quality4_garbage_manifest_falls_back_not_mqa():
    client = _client(
        {
            "HI_RES_LOSSLESS": {
                "manifest": base64.b64encode(b"not valid json").decode()
            },
            "LOSSLESS": _resp(_manifest(sample_rate=44100, bit_depth=16)),
        }
    )
    dl = arun(client.get_downloadable("1", 4))
    assert dl.sampling_rate == 44100
    assert client.requested == ["HI_RES_LOSSLESS", "LOSSLESS"]
    assert "HI_RES" not in client.requested


def test_quality4_both_unavailable_raises():
    client = _client({"HI_RES_LOSSLESS": {}, "LOSSLESS": {}})
    with pytest.raises(NonStreamableError):
        arun(client.get_downloadable("1", 4))
    assert set(client.requested) == {"HI_RES_LOSSLESS", "LOSSLESS"}


def test_quality4_mqa_codec_rejected():
    client = _client(
        {
            "HI_RES_LOSSLESS": _resp(
                _manifest(codecs="mqa", sample_rate=44100, bit_depth=24)
            ),
            "LOSSLESS": _resp(_manifest(sample_rate=44100, bit_depth=16)),
        }
    )
    dl = arun(client.get_downloadable("1", 4))
    assert dl.sampling_rate == 44100
    assert dl.bit_depth == 16
    assert client.requested == ["HI_RES_LOSSLESS", "LOSSLESS"]


# ===== from_tidal: HI_RES_LOSSLESS no longer KeyErrors =====


def _album_resp(audio_quality):
    return {
        "allowStreaming": True,
        "id": 1,
        "title": "Album",
        "releaseDate": "2020-01-01",
        "artists": [{"name": "Artist"}],
        "audioQuality": audio_quality,
        "cover": "",
    }


def test_track_from_tidal_maps_hires_lossless():
    album = AlbumMetadata.from_tidal(_album_resp("HI_RES_LOSSLESS"))
    track = {
        "id": 1,
        "title": "Title",
        "isrc": "ISRC",
        "artists": [{"name": "Artist"}],
        "audioQuality": "HI_RES_LOSSLESS",
    }
    meta = TrackMetadata.from_tidal(album, track)
    assert meta.info.quality == 4


def test_album_from_tidal_maps_hires_lossless():
    album = AlbumMetadata.from_tidal(_album_resp("HI_RES_LOSSLESS"))
    assert album.info.quality == 4


def test_album_from_tidal_playlist_track_resp_maps_hires_lossless():
    resp = {
        "allowStreaming": True,
        "id": 1,
        "album": {"title": "Album", "cover": ""},
        "streamStartDate": "2020-01-01",
        "artists": [{"name": "Artist"}],
        "audioQuality": "HI_RES_LOSSLESS",
    }
    album = AlbumMetadata.from_tidal_playlist_track_resp(resp)
    assert album.info.quality == 4
