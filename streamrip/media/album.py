import asyncio
import logging
import os
from dataclasses import dataclass

from .. import progress
from ..client import Client
from ..config import Config
from ..db import Database
from ..exceptions import NonStreamableError
from ..filepath_utils import clean_filepath
from ..metadata import AlbumMetadata
from ..metadata.util import get_album_track_ids
from .artwork import download_artwork
from .media import Media, Pending
from .track import PendingTrack

logger = logging.getLogger("streamrip")


def rename_to_match_quality(folder: str, meta: AlbumMetadata, filepaths_cfg) -> str:
    """Rename an album folder when the delivered stream's bit depth / sample
    rate differ from the pre-download placeholder that named it.

    The folder is created (PendingAlbum.resolve / PendingSingle) from album.info
    before any manifest is fetched, so a Tidal HiRes album can land in a folder
    labelled with the CD-quality placeholder. Once the tracks download and
    postprocess corrects album.info to the delivered values, recompute the leaf
    and move the folder. Returns the folder path (renamed, or unchanged on
    no-op / collision / failure).
    """
    new_leaf = clean_filepath(
        meta.format_folder_path(filepaths_cfg.folder_format),
        filepaths_cfg.restrict_characters,
    )
    new_folder = os.path.join(os.path.dirname(folder), new_leaf)
    if os.path.abspath(new_folder) == os.path.abspath(folder):
        return folder
    if os.path.exists(new_folder):
        logger.warning(
            "Cannot rename album folder to %s: target already exists; "
            "leaving tracks at %s.",
            new_folder,
            folder,
        )
        return folder
    try:
        os.rename(folder, new_folder)
    except OSError as e:
        logger.warning("Failed to rename %s -> %s: %s", folder, new_folder, e)
        return folder
    logger.info("Renamed album folder to match delivered quality: %s", new_folder)
    return new_folder


@dataclass(slots=True)
class Album(Media):
    meta: AlbumMetadata
    tracks: list[PendingTrack]
    config: Config
    # folder where the tracks will be downloaded
    folder: str
    db: Database

    async def preprocess(self):
        progress.add_title(self.meta.album)

    async def download(self):
        async def _resolve_and_download(pending: Pending):
            try:
                track = await pending.resolve()
                if track is None:
                    return
                await track.rip()
            except Exception as e:
                logger.error(f"Error downloading track: {e}")

        results = await asyncio.gather(
            *[_resolve_and_download(p) for p in self.tracks], return_exceptions=True
        )

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Album track processing error: {result}")

    async def postprocess(self):
        progress.remove_title(self.meta.album)
        # Tracks' postprocess corrected album.info to the delivered stream's
        # real bit depth / sample rate; rename the folder (named from the
        # pre-download placeholder) to match if it changed.
        self.folder = rename_to_match_quality(
            self.folder, self.meta, self.config.session.filepaths
        )


@dataclass(slots=True)
class PendingAlbum(Pending):
    id: str
    client: Client
    config: Config
    db: Database

    async def resolve(self) -> Album | None:
        try:
            resp = await self.client.get_metadata(self.id, "album")
        except NonStreamableError as e:
            logger.error(
                f"Album {self.id} not available to stream on {self.client.source} ({e})",
            )
            return None

        try:
            meta = AlbumMetadata.from_album_resp(resp, self.client.source)
        except Exception as e:
            logger.error(f"Error building album metadata for {id=}: {e}")
            return None

        if meta is None:
            logger.error(
                f"Album {self.id} not available to stream on {self.client.source}",
            )
            return None

        tracklist = get_album_track_ids(self.client.source, resp)
        folder = self.config.session.downloads.folder
        album_folder = self._album_folder(folder, meta)
        os.makedirs(album_folder, exist_ok=True)
        embed_cover, _ = await download_artwork(
            self.client.session,
            album_folder,
            meta.covers,
            self.config.session.artwork,
            for_playlist=False,
        )
        pending_tracks = [
            PendingTrack(
                id,
                album=meta,
                client=self.client,
                config=self.config,
                folder=album_folder,
                db=self.db,
                cover_path=embed_cover,
            )
            for id in tracklist
        ]
        logger.debug("Pending tracks: %s", pending_tracks)
        return Album(meta, pending_tracks, self.config, album_folder, self.db)

    def _album_folder(self, parent: str, meta: AlbumMetadata) -> str:
        config = self.config.session
        if config.downloads.source_subdirectories:
            parent = os.path.join(parent, self.client.source.capitalize())
        formatter = config.filepaths.folder_format
        folder = clean_filepath(
            meta.format_folder_path(formatter), config.filepaths.restrict_characters
        )

        return os.path.join(parent, folder)
