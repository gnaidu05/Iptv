"""Command-line interface for the m3u package.

Examples::

    python -m m3u info playlist.m3u
    python -m m3u ls playlist.m3u
    python -m m3u build song1.mp3 song2.mp3 -o out.m3u
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .model import Playlist
from .parser import parse_file


def _fmt_duration(seconds: int) -> str:
    if seconds < 0:
        return "--:--"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


def _cmd_info(args: argparse.Namespace) -> int:
    playlist = parse_file(args.file)
    streams = sum(1 for t in playlist if t.is_stream)
    print(f"File:     {args.file}")
    print(f"Tracks:   {len(playlist)}")
    print(f"Streams:  {streams}")
    print(f"Duration: {_fmt_duration(playlist.total_duration)}")
    return 0


def _cmd_ls(args: argparse.Namespace) -> int:
    playlist = parse_file(args.file)
    width = len(str(len(playlist)))
    for i, track in enumerate(playlist, start=1):
        dur = _fmt_duration(track.duration)
        print(f"{i:>{width}}. [{dur:>7}] {track}")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    playlist = Playlist()
    for path in args.paths:
        playlist.append(path)

    text = playlist.dumps(extended=not args.simple)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"Wrote {len(playlist)} tracks to {args.output}")
    else:
        sys.stdout.write(text)
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    from .checker import active_playlist, check_playlist

    playlist = parse_file(args.file)
    total = len(playlist)
    done = {"n": 0}

    def report(result) -> None:
        done["n"] += 1
        mark = "OK " if result.ok else "DEAD"
        if args.verbose or not result.ok:
            print(
                f"[{done['n']:>3}/{total}] {mark} {result.label} "
                f"({result.reason})",
                file=sys.stderr,
            )

    results = check_playlist(
        playlist,
        timeout=args.timeout,
        workers=args.workers,
        on_result=report,
    )

    active = active_playlist(results, attributes=playlist.attributes)
    alive = len(active)
    print(
        f"\nActive: {alive}/{total}  ({total - alive} dead)",
        file=sys.stderr,
    )

    text = active.dumps(extended=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"Wrote {alive} active channels to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="m3u", description="Work with M3U playlists.")
    parser.add_argument("--version", action="version", version=f"m3u {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="Show summary statistics for a playlist.")
    p_info.add_argument("file")
    p_info.set_defaults(func=_cmd_info)

    p_ls = sub.add_parser("ls", help="List the tracks in a playlist.")
    p_ls.add_argument("file")
    p_ls.set_defaults(func=_cmd_ls)

    p_build = sub.add_parser("build", help="Build a playlist from file paths.")
    p_build.add_argument("paths", nargs="+", help="Media paths or URLs.")
    p_build.add_argument("-o", "--output", help="Output file (default: stdout).")
    p_build.add_argument(
        "--simple",
        action="store_true",
        help="Emit a plain playlist without #EXTINF metadata.",
    )
    p_build.set_defaults(func=_cmd_build)

    p_check = sub.add_parser(
        "check", help="Probe each stream and emit only the active channels."
    )
    p_check.add_argument("file")
    p_check.add_argument("-o", "--output", help="Output file (default: stdout).")
    p_check.add_argument(
        "-t", "--timeout", type=float, default=12.0, help="Per-request timeout (s)."
    )
    p_check.add_argument(
        "-w", "--workers", type=int, default=24, help="Concurrent probes."
    )
    p_check.add_argument(
        "-v", "--verbose", action="store_true", help="Report every result, not just failures."
    )
    p_check.set_defaults(func=_cmd_check)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
