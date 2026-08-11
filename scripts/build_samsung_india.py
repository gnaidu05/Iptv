#!/usr/bin/env python3
"""Generate playlists/samsung-india.m3u from Samsung TV Plus' India region.

Samsung TV Plus publishes a free India storefront (~200 channels). Its streams
are **geo-locked to India** and use an ad-session-based CDN, so they will not
verify from outside India and will not play in the globally-hosted web STB.
This playlist is therefore kept SEPARATE from the health-check pipeline and the
STB — it is for use in a native player (VLC / a TV app) from within India.

Data source: the community mirror matthuisman/i.mjh.nz (Samsung TV Plus).
Stream URLs use Matt Huisman's jmp2.uk redirect, which resolves each channel id
to Samsung's current live URL.

Run from the repo root:  python scripts/build_samsung_india.py
"""

from __future__ import annotations

import gzip
import io
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "playlists", "samsung-india.m3u")

DATA_URL = "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/SamsungTVPlus/.channels.json.gz"
EPG_URL = "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/SamsungTVPlus/in.xml.gz"

HEADER = [
    f'#EXTM3U x-tvg-url="{EPG_URL}"',
    "# Samsung TV Plus - India region.",
    "# GEO-LOCKED TO INDIA: these streams need an India IP + the Samsung app",
    "# session; they will NOT play in the hosted web STB and are kept out of the",
    "# health-check pipeline. Use in a native player (VLC / TV app) from India.",
    "# Source: Samsung TV Plus via matthuisman/i.mjh.nz.",
]


def main() -> int:
    with urllib.request.urlopen(DATA_URL, timeout=60) as resp:
        data = json.load(io.BytesIO(gzip.decompress(resp.read())))

    channels = data["regions"]["in"]["channels"]
    lines = list(HEADER)
    for cid, c in sorted(channels.items(), key=lambda kv: kv[1].get("chno", 99999)):
        name = (c.get("name") or "").strip()
        logo = c.get("logo", "")
        group = c.get("group") or "Samsung TV Plus"
        lines.append(f'#EXTINF:-1 tvg-id="{cid}" tvg-logo="{logo}" group-title="{group}",{name}')
        lines.append(f"https://jmp2.uk/stvp-{cid}.m3u8")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {len(channels)} Samsung TV Plus India channels to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
