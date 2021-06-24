import asyncio
import os
from typing import List, Tuple
from urllib.parse import urlparse

import asyncspotify

__all__ = (
    "get_track_name",
    "get_track_names_from_playlist",
)


sp = asyncspotify.Client(asyncspotify.ClientCredentialsFlow(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
))


async def get_track_name(url: str) -> str:
    track_parsed = urlparse(url)
    track_id = track_parsed.path.replace("/track/", "")
    track = await sp.get_track(track_id)
    return track.name


async def get_track_names_from_playlist(url: str) -> Tuple[str, List[str]]:
    playlist_parsed = urlparse(url)
    playlist_id = playlist_parsed.path.replace("/playlist/", "")
    playlist = await sp.get_playlist(playlist_id)
    track_names = []
    async for track in playlist:
        track_names.append(f"{track.name} {', '.join([arts.name for arts in track.artists])}")
    return playlist.name, track_names


loop = asyncio.get_event_loop()
loop.create_task(sp.authorize())
