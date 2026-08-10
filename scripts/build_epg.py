#!/usr/bin/env python3
"""Build a compact EPG (now/next) database for the web STB.

Fetches Indian XMLTV guides (Tata Play + JioTV, community-maintained), matches
their programmes to the channels in playlists/india-active.m3u by normalised
display-name, and writes webstb/epg.json containing only our channels and only
a rolling time window — small enough to load instantly, same-origin, no CORS.

The STB computes "now / next" client-side from the absolute UTC timestamps, so
the guide stays correct until the next refresh (run a few times a day via the
epg GitHub Action).

Run from the repo root:  python scripts/build_epg.py
"""

from __future__ import annotations

import gzip
import io
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "m3u"))
import m3u  # noqa: E402

PLAYLIST = os.path.join(ROOT, "playlists", "india-active.m3u")
OUT = os.path.join(ROOT, "webstb", "epg.json")

SOURCES = [
    "https://raw.githubusercontent.com/mitthu786/tvepg/main/tataplay/epg.xml.gz",
    "https://raw.githubusercontent.com/mitthu786/tvepg/main/jiotv/epg.xml.gz",
]

WINDOW_BACK = 3 * 3600          # keep programmes ending within last 3h
WINDOW_FWD = 30 * 3600          # ...and starting within next 30h
TITLE_MAX = 70


def norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s or "")
    s = s.lower().replace("&", "and")
    s = re.sub(r"\b(fhd|uhd|4k)\b", "hd", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_xmltv_time(s: str) -> int:
    """'20260810213000 +0530' -> epoch seconds (UTC)."""
    s = s.strip()
    m = re.match(r"(\d{14})\s*([+-]\d{4})?", s)
    if not m:
        return 0
    dt = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    off = m.group(2)
    if off:
        sign = 1 if off[0] == "+" else -1
        mins = sign * (int(off[1:3]) * 60 + int(off[3:5]))
        dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp()) - mins * 60
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def fetch_guide(url: str):
    import requests

    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        data = r.content
        if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return ET.parse(io.BytesIO(data)).getroot()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {url}: {type(exc).__name__}")
        return None


def main() -> int:
    now = int(time.time())
    lo, hi = now - WINDOW_BACK, now + WINDOW_FWD

    # name -> list[(start, stop, title)]
    by_name: dict = {}
    for url in SOURCES:
        root = fetch_guide(url)
        if root is None:
            continue
        id_names: dict = {}
        for ch in root.findall("channel"):
            names = [norm(dn.text) for dn in ch.findall("display-name") if dn.text]
            id_names[ch.get("id")] = [n for n in names if n]
        added = 0
        for pr in root.findall("programme"):
            start = parse_xmltv_time(pr.get("start", ""))
            stop = parse_xmltv_time(pr.get("stop", ""))
            if not start or stop < lo or start > hi:
                continue
            title_el = pr.find("title")
            title = (title_el.text or "").strip()[:TITLE_MAX] if title_el is not None else ""
            for nm in id_names.get(pr.get("channel"), []):
                by_name.setdefault(nm, []).append((start, stop, title))
                added += 1
        print(f"  {url.split('/')[-2]}: {len(id_names)} channels, {added} programmes in window")

    # match to our channels
    playlist = m3u.parse_file(PLAYLIST)
    out_channels: dict = {}
    matched = 0
    for i, track in enumerate(playlist, start=1):
        key = norm(track.title)
        progs = by_name.get(key)
        if not progs:
            continue
        # dedupe by start time, sort chronologically
        seen = {}
        for s, e, t in progs:
            seen[s] = (s, e, t)
        rows = [list(v) for v in sorted(seen.values())]
        out_channels[str(i)] = rows
        matched += 1

    data = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": [lo, hi],
        "channels": out_channels,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(OUT)
    print(f"\nMatched EPG for {matched}/{len(playlist)} channels -> {OUT} ({size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
