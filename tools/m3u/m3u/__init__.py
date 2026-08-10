"""m3u - a small, dependency-free library for parsing and writing M3U/M3U8 playlists.

Typical usage::

    from m3u import Playlist

    playlist = Playlist.parse_file("playlist.m3u")
    for track in playlist:
        print(track.title, track.path)

    playlist.append("song.mp3", title="A Song", duration=210)
    playlist.write_file("out.m3u")
"""

from .model import Playlist, Track
from .parser import parse, parse_file
from .writer import dumps, dump_file

__all__ = [
    "Playlist",
    "Track",
    "parse",
    "parse_file",
    "dumps",
    "dump_file",
]

__version__ = "0.1.0"
