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
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "m3u"))

import m3u  # noqa: E402

# The STB lists every reachable HTTPS channel, but flags the ones that aren't
# CORS-playable with px:1. By default the app hides those (they'd show "NO
# SIGNAL"); when a CORS proxy is configured (web) or the native Android shell is
# running (?app=1), they are shown and routed so they play.
_WEB = os.path.join(ROOT, "playlists", "india-web.m3u")
_ACTIVE = os.path.join(ROOT, "playlists", "india-active.m3u")
PLAYLIST = _ACTIVE if os.path.exists(_ACTIVE) else _WEB
GEO_PLAYLIST = os.path.join(ROOT, "playlists", "india-geo.m3u")
LANG_MAP = os.path.join(ROOT, "playlists", "lang-map.json")
OUT = os.path.join(HERE, "channels.js")


def _web_urls():
    """URLs confirmed CORS-playable (india-web.m3u); everything else is px:1."""
    import re as _re
    if not os.path.exists(_WEB):
        return None  # no CORS data → treat all as playable
    txt = open(_WEB, encoding="utf-8").read()
    return set(_re.findall(r"https?://\S+", txt))

# URL (host+path) -> language, built from the iptv-org per-language feeds by
# scripts/refresh.py. Authoritative when present.
try:
    with open(LANG_MAP, encoding="utf-8") as _h:
        LANGMAP = json.load(_h)
except (OSError, ValueError):
    LANGMAP = {}

# Channel-id -> logo URL, from the iptv-org logo database (refreshed by
# scripts/refresh.py). Used to fill in logos for channels whose stream entry
# has no tvg-logo. Keyed by the base channel id (tvg-id without an @feed).
LOGOS_MAP = os.path.join(ROOT, "playlists", "logos.json")
try:
    with open(LOGOS_MAP, encoding="utf-8") as _h:
        LOGOS = json.load(_h)
except (OSError, ValueError):
    LOGOS = {}


def logo_for(tvg_logo: str, tvg_id: str) -> str:
    """Prefer the stream's own logo; otherwise look one up by channel id."""
    if tvg_logo:
        return tvg_logo
    base = (tvg_id or "").split("@")[0]
    return LOGOS.get(base, "")

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
INDIC_LANGS = {"Tamil", "Telugu", "Malayalam", "Kannada", "Bengali", "Marathi",
               "Punjabi", "Gujarati", "Odia", "Assamese", "Bhojpuri", "Hindi"}
# A foreign country/region in the name or in the iptv-org feed id (tvg-id after
# @) marks a diaspora/overseas feed. On its own that doesn't change the language
# (e.g. "Asianet Middle East" is still Malayalam), but a feed-map tag with no
# supporting keyword on such a channel is unreliable — see lang_of.
FOREIGN_RE = re.compile(
    r"\b(america|u\.?s\.?a|canada|australia|indonesia|indo-?china|malaysia|"
    r"singapore|dubai|u\.?a\.?e|qatar|middle east|europe|africa)\b", re.I)
# Clearly English national/global channels that feeds sometimes mis-tag onto an
# Indian language. Only brands that don't have a same-named regional variant.
ENGLISH_BRANDS_RE = re.compile(
    r"ndtv good times|\bgood times\b|\bwion\b|magellan ?tv|fashion ?tv|republic tv\b|"
    r"discovery (channel|kids|science|turbo|jeet)|investigation discovery|\btlc\b|"
    r"animal planet|travelxp|nat geo|national geographic", re.I)
# Unambiguous regional brands — trusted over a (sometimes wrong) feed-map tag.
# Kept deliberately narrow so ambiguous names (e.g. "Asianet Suvarna" = Kannada)
# are NOT caught.
STRONG_BRANDS = [
    ("Malayalam", re.compile(
        r"kaumudy|manorama|mazhavil|media ?one|flowers tv|amrita tv|"
        r"asianet (news|plus|movies|hd|middle)", re.I)),
]


def _urlkey(url: str) -> str:
    m = re.match(r"https?://([^/]+)(/[^?\s]*)", url or "")
    return f"{m.group(1).lower()}{m.group(2)}" if m else (url or "")


def _kw_lang(name: str):
    for lang, rx in LANG_KW_RE:
        if rx.search(name or ""):
            return lang
    return None


def _feed_id(tvg_id: str) -> str:
    return (tvg_id or "").split("@", 1)[1] if "@" in (tvg_id or "") else ""


def lang_of(name: str, url: str, group: str, tvg_id: str = "") -> str:
    for lang, rx in SCRIPT_RE:            # native script is unambiguous
        if rx.search(name or ""):
            return lang
    for lang, rx in STRONG_BRANDS:       # unambiguous regional brand beats the feed
        if rx.search(name or ""):
            return lang
    if ENGLISH_BRANDS_RE.search(name or ""):   # e.g. NDTV Good Times (not Tamil)
        return "English"
    mapped = LANGMAP.get(_urlkey(url))    # iptv-org feed classification
    kw = _kw_lang(name)                    # brand / word cue in the name
    foreign = bool(FOREIGN_RE.search(name or "") or FOREIGN_RE.search(_feed_id(tvg_id)))
    if mapped:
        # The feed tagged an Indian language, but if it's an overseas feed with
        # no keyword backing that language, the tag is unreliable → English.
        if mapped in INDIC_LANGS and kw != mapped and foreign:
            return "English"
        return mapped
    if kw:
        return kw
    if foreign:
        return "English"
    if group in ENGLISH_GROUPS:           # FAST movie/comedy/classic adds
        return "English"
    # Unmapped and not Indian by script/keyword: a Latin-script name is almost
    # always an English/global FAST channel (DD India, CNBC, the world FAST adds).
    n = name or ""
    if n and sum(c.isascii() for c in n) / len(n) > 0.85:
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


def write_playlist(path: str, channels: list, epg_url: str) -> int:
    """Write a single portable M3U mirroring the app lineup (one #EXTINF per
    channel, with tvg-id/tvg-logo/group-title). Channels without a stream URL
    (YouTube embeds) are skipped. Returns the number of entries written."""
    lines = ["#EXTM3U" + (f' x-tvg-url="{epg_url}"' if epg_url else "")]
    n = 0
    for ch in channels:
        url = (ch.get("url") or "").strip()
        if not url:
            continue  # YouTube-embed channels have no direct stream
        name = ch.get("name") or f"Channel {ch.get('num', '')}"
        attrs = [
            f'tvg-id="{ch.get("tvgId", "")}"',
            f'tvg-chno="{ch.get("num", "")}"',
            f'tvg-logo="{ch.get("logo", "")}"',
            f'group-title="{ch.get("group", "") or "General"}"',
        ]
        lines.append(f"#EXTINF:-1 {' '.join(attrs)},{name}")
        lines.append(url)
        n += 1
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return n


def apply_overrides(channels):
    """Swap specific channels' sources from playlists/overrides.json (keyed by
    tvg-id), applied after the refresh so the edits survive it. Used mainly to
    replace HEVC/HDR-only feeds with H.264 ones that phone browsers can decode."""
    path = os.path.join(ROOT, "playlists", "overrides.json")
    if not os.path.exists(path):
        return 0
    try:
        ov = json.load(open(path, encoding="utf-8"))
    except ValueError:
        return 0
    n = 0
    for ch in channels:
        o = ov.get(ch.get("tvgId", ""))
        if not isinstance(o, dict):
            continue
        if o.get("url"):
            ch["url"] = o["url"]
        for k in ("name", "group", "lang"):
            if o.get(k):
                ch[k] = o[k]
        if o.get("px"):
            ch["px"] = 1
        if "hevc" in o:              # allow forcing the flag off (known-good H.264)
            if o["hevc"]:
                ch["hevc"] = 1
            else:
                ch.pop("hevc", None)
            ch["hevcLock"] = 1       # don't let the probe overwrite an explicit choice
        n += 1
    return n


_HEVC_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
_CODEC_RE = re.compile(r'CODECS="([^"]*)"', re.I)
_STREAM_RE = re.compile(r"#EXT-X-STREAM-INF:", re.I)


def _probe_hevc(url):
    """Return True if the master playlist offers ONLY HEVC video (no H.264
    alternative) — those can't play in browsers without HEVC/MSE support.
    Returns False if any H.264 (avc1) variant exists, None if undetermined
    (unreachable, not a master, geo-blocked). Conservative: only True when
    positively confirmed, so working channels are never wrongly hidden."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _HEVC_UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=7) as r:
            text = r.read(20000).decode("utf-8", "replace")
    except Exception:
        return None
    if "#EXTM3U" not in text or not _STREAM_RE.search(text):
        return None  # not a master manifest (single variant / media playlist)
    codecs = " ".join(_CODEC_RE.findall(text)).lower()
    if not codecs:
        return None
    has_h264 = "avc1" in codecs or "avc3" in codecs
    has_hevc = "hev1" in codecs or "hvc1" in codecs or "dvh" in codecs
    if has_h264:
        return False
    if has_hevc:
        return True
    return None


def tag_hevc(channels):
    """Probe each non-geo live channel's master and tag HEVC-only ones with
    hevc=1, so the app can hide them on devices whose browser lacks HEVC. Uses
    playlists/hevc_cache.json (keyed by URL) so each weekly build only probes
    new/changed stream URLs. Never un-flags on a failed probe."""
    cache_path = os.path.join(ROOT, "playlists", "hevc_cache.json")
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
    except Exception:
        cache = {}

    # channels to probe: have a URL, not geo (geo = India-only, unreachable from
    # CI anyway), not a YouTube embed, not locked by an explicit override.
    todo = []
    for ch in channels:
        url = (ch.get("url") or "").strip()
        if not url or ch.get("yt") or ch.get("geo") or ch.get("hevcLock"):
            continue
        if url in cache:
            if cache[url]:
                ch["hevc"] = 1
            continue
        todo.append((ch, url))

    def work(item):
        ch, url = item
        return url, _probe_hevc(url)

    probed = 0
    if todo:
        with ThreadPoolExecutor(max_workers=24) as ex:
            for url, res in ex.map(work, todo):
                probed += 1
                if res is not None:
                    cache[url] = bool(res)
        # apply freshly-cached results
        for ch, url in todo:
            if cache.get(url):
                ch["hevc"] = 1
        try:
            json.dump(cache, open(cache_path, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))
        except Exception:
            pass

    hevc_n = sum(1 for c in channels if c.get("hevc"))
    # hevcLock is internal bookkeeping — don't ship it to the app
    for c in channels:
        c.pop("hevcLock", None)
    return hevc_n, probed


def main() -> int:
    pl = m3u.parse_file(PLAYLIST)
    webset = _web_urls()
    channels = []
    for i, track in enumerate(dedupe(list(pl)), start=1):
        attrs = track.attributes
        name = track.title or attrs.get("tvg-name") or f"Channel {i}"
        group = attrs.get("group-title", "") or "General"
        ch = {
            "num": i,
            "name": name,
            "url": track.path,
            "logo": logo_for(attrs.get("tvg-logo", ""), attrs.get("tvg-id", "")),
            "group": group,
            "tvgId": attrs.get("tvg-id", ""),
            "lang": lang_of(name, track.path, group, attrs.get("tvg-id", "")),
        }
        if webset is not None and track.path not in webset:
            ch["px"] = 1  # not CORS-playable: needs the proxy / native shell
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
                    "logo": logo_for(a.get("tvg-logo", ""), a.get("tvg-id", "")),
                    "group": ggroup,
                    "tvgId": a.get("tvg-id", ""),
                    "lang": lang_of(gname, track.path, ggroup, a.get("tvg-id", "")),
                    "geo": 1,
                }
            )
        geo_n = len(geo)

    # Manually-curated extras (e.g. official YouTube live channels), played via
    # an embed iframe rather than HLS. Kept in playlists/extras.json so they
    # survive the weekly refresh.
    extras_n = 0
    extras_path = os.path.join(ROOT, "playlists", "extras.json")
    if os.path.exists(extras_path):
        try:
            extras = json.load(open(extras_path, encoding="utf-8"))
        except ValueError:
            extras = []
        base = len(channels)
        for k, ex in enumerate(extras):
            if ex.get("yt"):
                channels.append(
                    {
                        "num": base + k + 1,
                        "name": ex.get("name", f"Channel {base + k + 1}"),
                        "url": "",
                        "logo": ex.get("logo", ""),
                        "group": ex.get("group", "") or "General",
                        "tvgId": "",
                        "lang": ex.get("lang", "Other"),
                        "yt": ex["yt"],
                        "ytlive": 1 if ex.get("ytlive") else 0,
                    }
                )
                extras_n += 1
            elif ex.get("url"):           # a direct HLS/proxy channel
                ch = {
                    "num": base + k + 1,
                    "name": ex.get("name", f"Channel {base + k + 1}"),
                    "url": ex["url"],
                    "logo": ex.get("logo", ""),
                    "group": ex.get("group", "") or "General",
                    "tvgId": "",
                    "lang": ex.get("lang", "Other"),
                }
                if ex.get("px"):          # needs the CORS proxy (non-CORS segments)
                    ch["px"] = 1
                channels.append(ch)
                extras_n += 1

    # Per-channel source overrides (e.g. swap an HEVC-only feed for H.264), then
    # tag the remaining HEVC-only channels so the app can hide them on devices
    # whose browser can't decode HEVC.
    ovr_n = apply_overrides(channels)
    hevc_n, hevc_probed = tag_hevc(channels)

    # Public-domain / freely-licensed on-demand movies (Internet Archive), kept
    # in playlists/movies.json. These are VOD (individual .mp4 files played with
    # a seek bar), not live channels, so they live in a separate list and never
    # enter the channel lineup or the portable playlist.
    vod = []
    vod_path = os.path.join(ROOT, "playlists", "movies.json")
    if os.path.exists(vod_path):
        try:
            for m in json.load(open(vod_path, encoding="utf-8")):
                if m.get("url"):
                    vod.append({
                        "name": m.get("name", "Movie"),
                        "url": m["url"],
                        "logo": m.get("logo", ""),
                        "group": m.get("group", "") or "Movies",
                    })
        except ValueError:
            vod = []

    # Public-domain / freely-licensed on-demand TV series (Internet Archive),
    # kept in playlists/series.json: a list of shows, each with its episodes.
    # Also VOD (seekable .mp4), kept separate from the channel lineup.
    series = []
    series_path = os.path.join(ROOT, "playlists", "series.json")
    if os.path.exists(series_path):
        try:
            for s in json.load(open(series_path, encoding="utf-8")):
                eps = [e for e in s.get("episodes", []) if e.get("url")]
                if eps:
                    series.append({
                        "show": s.get("show", "Series"),
                        "genre": s.get("genre", "") or "Series",
                        "logo": s.get("logo", ""),
                        "episodes": [{"title": e.get("title", "Episode"), "url": e["url"]} for e in eps],
                    })
        except ValueError:
            series = []

    epg_url = pl.attributes.get("x-tvg-url", "")
    data = {"epg": epg_url, "channels": channels}
    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write("// Auto-generated by build.py from playlists/india-active.m3u\n")
        handle.write("window.STB_DATA = ")
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write(";\n")
        handle.write("window.STB_VOD = ")
        json.dump(vod, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write(";\n")
        handle.write("window.STB_SERIES = ")
        json.dump(series, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write(";\n")

    # Also emit a single portable playlist that mirrors the app's lineup, so it
    # can be dropped into VLC / any IPTV player and stays current with each
    # weekly refresh. YouTube-embed channels have no stream URL, so they're
    # skipped here.
    aura_m3u = os.path.join(ROOT, "playlists", "aura.m3u")
    m3u_n = write_playlist(aura_m3u, channels, epg_url)

    with_logo = sum(1 for c in channels if c["logo"])
    fd = [c["name"] for c in channels if c.get("fd")]
    px = sum(1 for c in channels if c.get("px"))
    print(f"Wrote {len(channels)} channels ({with_logo} with logos) to {OUT}")
    print(f"DD Free Dish bouquet: {len(fd)} channels")
    print(f"India (geo-blocked) group: {geo_n} channels")
    print(f"Non-CORS (px, need proxy/native): {px} channels")
    print(f"Extras (YouTube live): {extras_n} channels")
    print(f"Source overrides applied: {ovr_n}")
    print(f"HEVC-only channels tagged: {hevc_n} (probed {hevc_probed} this run)")
    print(f"On-demand movies (VOD): {len(vod)} titles")
    print(f"On-demand series (VOD): {len(series)} shows, {sum(len(s['episodes']) for s in series)} episodes")
    print(f"Portable playlist: {m3u_n} entries -> {aura_m3u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
