"""Parsing of M3U / extended M3U (``#EXTM3U``) playlists."""

from __future__ import annotations

import re
from typing import List, Tuple

from .model import Playlist, Track

# Matches: #EXTINF:<duration> <attributes>,<title>
_EXTINF_RE = re.compile(r"^#EXTINF:(?P<duration>-?\d+)(?P<attrs>[^,]*),(?P<title>.*)$")
# Matches key="value" attribute pairs inside an EXTINF line.
_ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def _parse_extinf(line: str) -> Tuple[int, str, dict]:
    """Return (duration, title, attributes) from an ``#EXTINF`` line."""
    match = _EXTINF_RE.match(line)
    if not match:
        return -1, "", {}

    try:
        duration = int(match.group("duration"))
    except ValueError:
        duration = -1

    attributes = dict(_ATTR_RE.findall(match.group("attrs")))
    title = match.group("title").strip()
    return duration, title, attributes


def parse(text: str) -> Playlist:
    """Parse M3U/M3U8 text into a :class:`Playlist`.

    Handles both the plain form (one path per line) and the extended
    ``#EXTM3U`` form with ``#EXTINF`` metadata lines. Comments and blank
    lines are ignored.
    """
    playlist = Playlist()
    pending_duration = -1
    pending_title = None
    pending_attrs: dict = {}
    pending_vlc: dict = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#"):
            if line.startswith("#EXTM3U"):
                playlist.attributes.update(_ATTR_RE.findall(line))
            elif line.startswith("#EXTINF:"):
                pending_duration, pending_title, pending_attrs = _parse_extinf(line)
            elif line.startswith("#EXTVLCOPT:"):
                option = line[len("#EXTVLCOPT:"):]
                if "=" in option:
                    key, value = option.split("=", 1)
                    pending_vlc[key.strip()] = value.strip()
            # Other directives (#EXTM3U, #PLAYLIST, comments) carry no per-track state.
            continue

        playlist.tracks.append(
            Track(
                path=line,
                title=pending_title,
                duration=pending_duration,
                attributes=pending_attrs,
                vlc_options=pending_vlc,
            )
        )
        pending_duration = -1
        pending_title = None
        pending_attrs = {}
        pending_vlc = {}

    return playlist


def parse_file(path: str, encoding: str = "utf-8") -> Playlist:
    """Read and parse a playlist from disk."""
    with open(path, "r", encoding=encoding) as handle:
        return parse(handle.read())
