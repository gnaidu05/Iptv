"""Serialization of playlists back to M3U text."""

from __future__ import annotations

from .model import Playlist, Track


def _format_extinf(track: Track) -> str:
    attrs = ""
    if track.attributes:
        attrs = " " + " ".join(f'{k}="{v}"' for k, v in track.attributes.items())
    title = track.title or ""
    return f"#EXTINF:{track.duration}{attrs},{title}"


def dumps(playlist: Playlist, extended: bool = True) -> str:
    """Serialize a playlist to a string.

    When ``extended`` is true (the default) an ``#EXTM3U`` header and
    ``#EXTINF`` lines are emitted; otherwise a plain path-per-line file is
    produced.
    """
    lines = []
    if extended:
        header = "#EXTM3U"
        if playlist.attributes:
            header += " " + " ".join(
                f'{k}="{v}"' for k, v in playlist.attributes.items()
            )
        lines.append(header)
        for track in playlist:
            lines.append(_format_extinf(track))
            for key, value in track.vlc_options.items():
                lines.append(f"#EXTVLCOPT:{key}={value}")
            lines.append(track.path)
    else:
        for track in playlist:
            lines.append(track.path)

    return "\n".join(lines) + "\n"


def dump_file(
    playlist: Playlist,
    path: str,
    extended: bool = True,
    encoding: str = "utf-8",
) -> None:
    """Write a playlist to disk."""
    with open(path, "w", encoding=encoding) as handle:
        handle.write(dumps(playlist, extended=extended))
