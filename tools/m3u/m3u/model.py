"""Data model for M3U playlists."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional


@dataclass
class Track:
    """A single entry in a playlist.

    Attributes:
        path: The media resource — a local path or a URL.
        title: Human-readable display title (from ``#EXTINF``).
        duration: Length in seconds; ``-1`` means unknown/stream.
        attributes: Extra ``#EXTINF`` key="value" attributes such as
            ``tvg-id`` or ``group-title`` used by IPTV playlists.
        vlc_options: ``#EXTVLCOPT`` options that precede the URL, e.g.
            ``http-referrer`` and ``http-user-agent``.
    """

    path: str
    title: Optional[str] = None
    duration: int = -1
    attributes: dict = field(default_factory=dict)
    vlc_options: dict = field(default_factory=dict)

    @property
    def is_stream(self) -> bool:
        """True when the entry points at a network resource."""
        return "://" in self.path

    def __str__(self) -> str:
        return self.title or self.path


class Playlist:
    """An ordered collection of :class:`Track` objects."""

    def __init__(
        self,
        tracks: Optional[Iterable[Track]] = None,
        attributes: Optional[dict] = None,
    ) -> None:
        self.tracks: List[Track] = list(tracks) if tracks else []
        # Attributes on the ``#EXTM3U`` header line, e.g. ``x-tvg-url``.
        self.attributes: dict = dict(attributes) if attributes else {}

    # -- construction helpers -------------------------------------------------
    @classmethod
    def parse(cls, text: str) -> "Playlist":
        from .parser import parse

        return parse(text)

    @classmethod
    def parse_file(cls, path: str, encoding: str = "utf-8") -> "Playlist":
        from .parser import parse_file

        return parse_file(path, encoding=encoding)

    # -- mutation -------------------------------------------------------------
    def append(
        self,
        path: str,
        title: Optional[str] = None,
        duration: int = -1,
        vlc_options: Optional[dict] = None,
        **attributes,
    ) -> Track:
        """Add a track and return it."""
        track = Track(
            path=path,
            title=title,
            duration=duration,
            attributes=attributes,
            vlc_options=vlc_options or {},
        )
        self.tracks.append(track)
        return track

    def extend(self, tracks: Iterable[Track]) -> None:
        self.tracks.extend(tracks)

    def remove(self, track: Track) -> None:
        self.tracks.remove(track)

    # -- serialization --------------------------------------------------------
    def dumps(self, extended: bool = True) -> str:
        from .writer import dumps

        return dumps(self, extended=extended)

    def write_file(self, path: str, extended: bool = True, encoding: str = "utf-8") -> None:
        from .writer import dump_file

        dump_file(self, path, extended=extended, encoding=encoding)

    # -- total duration -------------------------------------------------------
    @property
    def total_duration(self) -> int:
        """Sum of known (non-negative) track durations, in seconds."""
        return sum(t.duration for t in self.tracks if t.duration > 0)

    # -- container protocol ---------------------------------------------------
    def __iter__(self) -> Iterator[Track]:
        return iter(self.tracks)

    def __len__(self) -> int:
        return len(self.tracks)

    def __getitem__(self, index):
        return self.tracks[index]

    def __eq__(self, other) -> bool:
        return isinstance(other, Playlist) and self.tracks == other.tracks

    def __repr__(self) -> str:
        return f"Playlist({len(self.tracks)} tracks)"
