"""Reachability checking for playlist entries.

The checker performs a lightweight HTTP request against each track's URL and
decides whether the stream is *active*. For HLS (``.m3u8``) endpoints it
verifies that the response body actually looks like an HLS manifest
(``#EXTM3U``); for other endpoints an HTTP 200 with a media-ish content type
is accepted.

``requests`` is an optional dependency — installed via ``pip install
m3u[check]`` — because it is only needed for this module.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, List, Optional

from .model import Playlist, Track

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class CheckResult:
    """Outcome of probing a single track."""

    track: Track
    ok: bool
    status: Optional[int] = None
    reason: str = ""

    @property
    def label(self) -> str:
        return str(self.track)


def _headers_for(track: Track) -> dict:
    """Build request headers, honouring ``#EXTVLCOPT`` hints."""
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    opts = track.vlc_options
    if "http-user-agent" in opts:
        headers["User-Agent"] = opts["http-user-agent"]
    referrer = opts.get("http-referrer") or opts.get("http-referer")
    if referrer:
        headers["Referer"] = referrer
    if "http-origin" in opts:
        headers["Origin"] = opts["http-origin"]
    return headers


def check_track(track: Track, timeout: float = 12.0) -> CheckResult:
    """Probe a single track and return a :class:`CheckResult`."""
    import requests

    url = track.path
    headers = _headers_for(track)

    try:
        resp = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            stream=True,
            allow_redirects=True,
        )
    except requests.exceptions.RequestException as exc:
        return CheckResult(track, ok=False, reason=type(exc).__name__)

    try:
        status = resp.status_code
        if status != 200:
            return CheckResult(track, ok=False, status=status, reason=f"HTTP {status}")

        # Read only the first chunk — manifests are tiny, and we do not want to
        # pull down live segments.
        try:
            head = next(resp.iter_content(chunk_size=2048), b"") or b""
        except requests.exceptions.RequestException as exc:
            return CheckResult(track, ok=False, status=status, reason=type(exc).__name__)

        text = head.decode("utf-8", "ignore")
        content_type = resp.headers.get("Content-Type", "").lower()

        is_hls_url = ".m3u8" in url.lower()
        looks_like_manifest = "#EXTM3U" in text
        media_content_type = any(
            hint in content_type
            for hint in ("mpegurl", "octet-stream", "video", "audio", "mp2t")
        )

        if is_hls_url:
            if looks_like_manifest:
                return CheckResult(track, ok=True, status=status, reason="manifest")
            return CheckResult(
                track, ok=False, status=status, reason="200 but no #EXTM3U"
            )

        # Non-.m3u8 endpoint (e.g. a repackaging proxy): accept on media type
        # or an embedded manifest.
        if looks_like_manifest or media_content_type:
            return CheckResult(track, ok=True, status=status, reason="media")
        return CheckResult(track, ok=False, status=status, reason="not media")
    finally:
        resp.close()


def check_playlist(
    playlist: Playlist,
    timeout: float = 12.0,
    workers: int = 24,
    on_result: Optional[Callable[[CheckResult], None]] = None,
) -> List[CheckResult]:
    """Probe every track concurrently.

    Results are returned in the playlist's original order. ``on_result`` is
    invoked (from worker threads) as each check finishes, useful for progress
    reporting.
    """
    results: List[Optional[CheckResult]] = [None] * len(playlist)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_index = {
            pool.submit(check_track, track, timeout): i
            for i, track in enumerate(playlist)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            result = future.result()
            results[index] = result
            if on_result is not None:
                on_result(result)

    return [r for r in results if r is not None]


def active_playlist(
    results: List[CheckResult], attributes: Optional[dict] = None
) -> Playlist:
    """Build a new playlist containing only the reachable tracks.

    ``attributes`` (e.g. the source playlist's ``#EXTM3U`` header attributes
    such as ``x-tvg-url``) are carried onto the new playlist.
    """
    return Playlist((r.track for r in results if r.ok), attributes=attributes)
