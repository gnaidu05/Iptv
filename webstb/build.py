#!/usr/bin/env python3
"""Regenerate webstb/channels.js from the active playlist.

Run from the repo root after refreshing playlists/india-active.m3u:

    python webstb/build.py

It reads playlists/india-active.m3u using the bundled m3u library and writes
the channel database (name, url, logo, group, tvg-id) that the set-top box UI
loads at boot.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "m3u"))

import m3u  # noqa: E402

PLAYLIST = os.path.join(ROOT, "playlists", "india-active.m3u")
GEO_PLAYLIST = os.path.join(ROOT, "playlists", "india-geo.m3u")
LANG_MAP = os.path.join(ROOT, "playlists", "lang-map.json")
OUT = os.path.join(HERE, "channels.js")

# URL (host+path) -> language, built from the iptv-org per-language feeds by
# scripts/refresh.py. Authoritative when present.
try:
    with open(LANG_MAP, encoding="utf-8") as _h:
        LANGMAP = json.load(_h)
except (OSError, ValueError):
    LANGMAP = {}

# Native-script ranges: a channel name written in a script names its language.
SCRIPTS = [
    ("Tamil", "஀-௿"), ("Telugu", "ఀ-౿"),
    ("Kannada", "ಀ-೿"), ("Malayalam", "ഀ-ൿ"),
    ("Bengali", "ঀ-৿"), ("Gujarati", "઀-૿"),
    ("Punjabi", "਀-੿"), ("Odia", "଀-୿"),
]
SCRIPT_RE = [(lang, re.compile("[" + rng + "]")) for lang, rng in SCRIPTS]

# Brand / word cues for channels whose name has no native script and that are
# not in the feed map (e.g. FAST additions).
LANG_KEYWORDS = [
    ("Malayalam", r"malayalam|asianet|manorama|mazhavil|kairali|amrita|surya tv|flowers|kaumudy|media ?one|24 ?news mal"),
    ("Tamil", r"\btamil\b|polimer|kalaignar|adithya|jaya tv|vijay|sun music|sun tv|k tv|raj tv|raj digital"),
    ("Telugu", r"\btelugu\b|etv|ntv|tv9 telugu|sakshi|abn|10tv|t news|bhakthi|zee thirai"),
    ("Kannada", r"\bkannada\b|udaya|colors kannada|public tv"),
    ("Bengali", r"\bbengali\b|\bbangla\b|aakaash|aamar|tara news|jalsha"),
    ("Marathi", r"\bmarathi\b|marathibana"),
    ("Punjabi", r"\bpunjabi\b|\bptc\b|chardikla|balle|5aab"),
    ("Gujarati", r"\bgujarati\b"),
    ("Odia", r"\bodia\b|odisha|kalinga"),
    ("Bhojpuri", r"bhojpuri|filamchi|oscar movies bho"),
    ("Hindi", r"\bhindi\b|aaj tak|abp|ndtv india|zee news|india tv|dd national|dd news|dd bharati|"
              r"sansad|sansad tv|\b9x|b4u|aastha|sanskar|sadhna|sadhana|satsang|shraddha|shubh|"
              r"paras|arihant|ganga|nazara|goldmines|dangal|enterr|manoranjan|maha movie|wow |"
              r"mastiii|dhamaal|dhinchaak|dabangg|ishara|sony pal|big magic|naaptol|news24|"
              r"news nation|bharat 24|bharat24|republic bharat|good news today|shemaroo|dd kisan|dd urdu"),
]
LANG_KW_RE = [(lang, re.compile(pat, re.I)) for lang, pat in LANG_KEYWORDS]
# FAST channels we add are English-language unless clearly Indian.
ENGLISH_GROUPS = {"Movies", "Comedy", "Classic TV"}


def _urlkey(url: str) -> str:
    m = re.match(r"https?://([^/]+)(/[^?\s]*)", url or "")
    return f"{m.group(1).lower()}{m.group(2)}" if m else (url or "")


def lang_of(name: str, url: str, group: str) -> str:
    for lang, rx in SCRIPT_RE:            # native script is unambiguous
        if rx.search(name or ""):
            return lang
    mapped = LANGMAP.get(_urlkey(url))    # iptv-org feed classification
    if mapped:
        return mapped
    for lang, rx in LANG_KW_RE:           # brand / word cues
        if rx.search(name or ""):
            return lang
    if group in ENGLISH_GROUPS:           # FAST movie/comedy/classic adds
        return "English"
    return "Other"

# DD Free Dish bouquet membership. All Doordarshan channels plus the private
# free-to-air channels carried on DD Free Dish. The private lineup shifts with
# quarterly auctions, so this keyword list is best-effort and easy to edit.
FREE_DISH_KEYWORDS = [
    "sansad",
    # movies
    "goldmines", "dangal", "enterr", "manoranjan", "bhojpuri cinema",
    "b4u kadak", "b4u bhojpuri", "wow cinema", "maha movie", "nazara",
    "dhinchaak", "dabangg", "filamchi", "abzy", "cinema tv", "shemaroo",
    "sony pal", "ishara",
    # music
    "b4u music", "wow music", "mastiii", "9x jhakaas", "9xm", "dhoom",
    # devotional
    "aastha", "sanskar", "shubh", "ishwar", "paras tv", "sadhna", "satsang",
    "shraddha", "channel divya", "arihant", "peace of mind", "sanatan",
    # free-to-air news carried on Free Dish
    "news24", "news 24", "news nation", "bharat24", "bharat 24",
    "republic bharat", "good news today",
]


def is_free_dish(name: str) -> bool:
    n = re.sub(r"\s*\(.*?\)\s*", " ", name or "").strip().lower()
    if n.startswith("dd ") or n == "dd":
        return True
    return any(kw in n for kw in FREE_DISH_KEYWORDS)


def norm_name(name: str) -> str:
    """Collapse a channel name to a dedupe key: drop (720p)/quality/HD-SD tags
    and punctuation, so 'Aaj Tak', 'Aaj Tak (720p)' and 'Aaj Tak HD (1080p)' all
    map to the same key. Digits are kept, so 'Star Sports 1' and '2' stay apart."""
    n = (name or "").lower()
    n = re.sub(r"\(.*?\)", " ", n)                       # (720p), (Not 24/7)…
    n = re.sub(r"\[.*?\]", " ", n)                       # [Geo-blocked]…
    n = re.sub(r"\b(fhd|uhd|hd|sd|4k|hevc|h265|h264)\b", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n).strip()
    return re.sub(r"\s+", " ", n)


def _is_hd(name: str) -> bool:
    return bool(re.search(r"\b(hd|fhd|uhd|4k|1080|1440|2160)\b", (name or "").lower()))


def dedupe(tracks):
    """Keep one track per normalised name. Prefer an HD variant, then one with a
    logo, else the first seen. Order follows the kept track's first appearance."""
    order, best = [], {}
    for t in tracks:
        key = norm_name(t.title or "") or ("__" + t.path)
        if key not in best:
            order.append(key)
            best[key] = t
        else:
            cur = best[key]
            cand = (_is_hd(t.title or ""), bool(t.attributes.get("tvg-logo")))
            have = (_is_hd(cur.title or ""), bool(cur.attributes.get("tvg-logo")))
            if cand > have:
                best[key] = t
    return [best[k] for k in order]


def main() -> int:
    pl = m3u.parse_file(PLAYLIST)
    channels = []
    for i, track in enumerate(dedupe(list(pl)), start=1):
        attrs = track.attributes
        name = track.title or attrs.get("tvg-name") or f"Channel {i}"
        group = attrs.get("group-title", "") or "General"
        ch = {
            "num": i,
            "name": name,
            "url": track.path,
            "logo": attrs.get("tvg-logo", ""),
            "group": group,
            "tvgId": attrs.get("tvg-id", ""),
            "lang": lang_of(name, track.path, group),
        }
        if is_free_dish(name):
            ch["fd"] = 1
        channels.append(ch)

    # India geo-blocked channels (403/401 from CI, usually work from India) —
    # appended as a separate, flagged group so they surface in their own tab.
    geo_n = 0
    if os.path.exists(GEO_PLAYLIST):
        geo = dedupe(list(m3u.parse_file(GEO_PLAYLIST)))
        base = len(channels)
        for j, track in enumerate(geo):
            a = track.attributes
            gname = track.title or f"Channel {base + j + 1}"
            ggroup = a.get("group-title", "") or "India"
            channels.append(
                {
                    "num": base + j + 1,
                    "name": gname,
                    "url": track.path,
                    "logo": a.get("tvg-logo", ""),
                    "group": ggroup,
                    "tvgId": a.get("tvg-id", ""),
                    "lang": lang_of(gname, track.path, ggroup),
                    "geo": 1,
                }
            )
        geo_n = len(geo)

    data = {"epg": pl.attributes.get("x-tvg-url", ""), "channels": channels}
    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write("// Auto-generated by build.py from playlists/india-active.m3u\n")
        handle.write("window.STB_DATA = ")
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write(";\n")

    with_logo = sum(1 for c in channels if c["logo"])
    fd = [c["name"] for c in channels if c.get("fd")]
    print(f"Wrote {len(channels)} channels ({with_logo} with logos) to {OUT}")
    print(f"DD Free Dish bouquet: {len(fd)} channels")
    print(f"India (geo-blocked) group: {geo_n} channels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
