#!/usr/bin/env python3
"""Build a compact EPG (now/next) database for the web STB.

Fetches several Indian XMLTV guides, matches their programmes to the channels
in playlists/india-active.m3u by name, and writes webstb/epg.json containing
only our channels and only a rolling time window — small enough to load
instantly, same-origin, no CORS.

Feeds are parsed in a streaming fashion (iterparse) to keep memory bounded even
for the large epgshare guide. Matching is exact-normalised first, then a
guarded fuzzy fallback (same digits + same HD/SD flag) to absorb spelling and
word-order variants like "Andhra Jyoti" vs "Andhra Jyothi".

Run from the repo root:  python scripts/build_epg.py
"""

from __future__ import annotations

import difflib
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

# Community-maintained Indian XMLTV guides (fetched server-side, so CORS is
# irrelevant). Order matters only for which source's title wins on a tie.
SOURCES = [
    "https://raw.githubusercontent.com/mitthu786/tvepg/main/tataplay/epg.xml.gz",
    "https://raw.githubusercontent.com/mitthu786/tvepg/main/jiotv/epg.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_IN1.xml.gz",
]

WINDOW_BACK = 3 * 3600
WINDOW_FWD = 30 * 3600
TITLE_MAX = 70
FUZZY_CUTOFF = 0.80


def norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s or "")
    s = s.lower().replace("&", "and")
    s = re.sub(r"\b(fhd|uhd|4k)\b", "hd", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# tokens that carry no brand identity — a match resting only on these is weak
GENERIC = {"tv", "hd", "sd", "channel", "news", "music", "movie", "movies",
           "cinema", "plus", "network", "the", "india", "live", "hindi", "digital"}


def lev(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _contig(short, long) -> bool:
    for i in range(len(long) - len(short) + 1):
        if long[i:i + len(short)] == short:
            return True
    return False


def fuzzy_ok(ot, ct) -> bool:
    """True only when two token lists are the same channel spelled differently.

    Guards against near-miss brand collisions (Odisha/Disha, ETV/VTV, 7S/7X):
    a single differing token is allowed only for genuine spelling variants
    (small edit distance on long-enough tokens), and stricter still when the
    only shared context is generic words like "tv"/"news".
    """
    if ot == ct:
        return True
    # a bare number token distinguishes sibling channels (Goldmines / Goldmines 2,
    # Star Sports 1 / 2) — the numeric tokens must match exactly
    nums = lambda toks: {t for t in toks if t.isdigit()}
    if nums(ot) != nums(ct):
        return False
    if len(ot) != len(ct):
        short, long = (ot, ct) if len(ot) < len(ct) else (ct, ot)
        if not _contig(short, long):
            return False
        return any(tok not in GENERIC for tok in short)  # need a real brand token
    mism = [(a, b) for a, b in zip(ot, ct) if a != b]
    if len(mism) != 1:
        return False
    a, b = mism[0]
    ed, ml = lev(a, b), min(len(a), len(b))
    strong = any(tok not in GENERIC for a2, b2 in zip(ot, ct) if a2 == b2 for tok in (a2,))
    if strong:
        return (ed <= 1 and ml >= 5) or (ed <= 2 and ml >= 7)
    return (ed <= 1 and ml >= 6) or (ed <= 2 and ml >= 8)


def parse_xmltv_time(s: str) -> int:
    s = (s or "").strip()
    m = re.match(r"(\d{14})\s*([+-]\d{4})?", s)
    if not m:
        return 0
    dt = datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    base = int(dt.timestamp())
    off = m.group(2)
    if off:
        sign = 1 if off[0] == "+" else -1
        base -= sign * (int(off[1:3]) * 60 + int(off[3:5])) * 60
    return base


def fetch_bytes(url: str):
    import requests

    r = requests.get(url, timeout=90)
    r.raise_for_status()
    data = r.content
    if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def harvest(url: str, lo: int, hi: int, by_name: dict) -> None:
    """Stream a guide and append in-window programmes into by_name[name]."""
    try:
        data = fetch_bytes(url)
    except Exception as exc:  # noqa: BLE001 - a flaky feed must not abort the build
        print(f"  ! {url}: {type(exc).__name__}")
        return

    id_names: dict = {}
    added = 0
    ctx = ET.iterparse(io.BytesIO(data), events=("end",))
    for _, el in ctx:
        if el.tag == "channel":
            names = [norm(dn.text) for dn in el.findall("display-name") if dn.text]
            id_names[el.get("id")] = [n for n in names if n]
            el.clear()
        elif el.tag == "programme":
            start = parse_xmltv_time(el.get("start", ""))
            stop = parse_xmltv_time(el.get("stop", ""))
            if start and stop >= lo and start <= hi:
                t_el = el.find("title")
                title = (t_el.text or "").strip()[:TITLE_MAX] if t_el is not None else ""
                for nm in id_names.get(el.get("channel"), []):
                    by_name.setdefault(nm, []).append((start, stop, title))
                    added += 1
            el.clear()
    print(f"  {url.split('/')[-2] if '/' in url else url}: "
          f"{len(id_names)} channels, {added} programmes in window")


def match_key(title: str, by_name: dict, epg_names, compact_index) -> str:
    key = norm(title)
    if key in by_name:
        return key
    ck = key.replace(" ", "")
    if ck in compact_index:
        return compact_index[ck]
    kt = key.split()
    for cand in difflib.get_close_matches(key, epg_names, n=8, cutoff=FUZZY_CUTOFF):
        if fuzzy_ok(kt, cand.split()):
            return cand
    return ""


def main() -> int:
    now = int(time.time())
    lo, hi = now - WINDOW_BACK, now + WINDOW_FWD

    by_name: dict = {}
    for url in SOURCES:
        harvest(url, lo, hi, by_name)

    epg_names = list(by_name.keys())
    compact_index: dict = {}
    for nm in epg_names:
        compact_index.setdefault(nm.replace(" ", ""), nm)

    playlist = m3u.parse_file(PLAYLIST)
    out_channels: dict = {}
    matched = fuzzy = 0
    for i, track in enumerate(playlist, start=1):
        key = match_key(track.title, by_name, epg_names, compact_index)
        if not key:
            continue
        if norm(track.title) != key:
            fuzzy += 1
        seen = {}
        for s, e, t in by_name[key]:
            seen[s] = (s, e, t)
        out_channels[str(i)] = [list(v) for v in sorted(seen.values())]
        matched += 1

    data = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": [lo, hi],
        "channels": out_channels,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(OUT)
    print(f"\nMatched EPG for {matched}/{len(playlist)} channels "
          f"({fuzzy} via fuzzy) -> {OUT} ({size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
