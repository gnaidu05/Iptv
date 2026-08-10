# India playlist — link check report

Generated with `python -m m3u check`. Each stream URL was fetched and, for HLS
endpoints, verified to return HTTP 200 with a valid `#EXTM3U` manifest.

> **Point-in-time snapshot.** Live IPTV streams flap; channels move between
> "active" and "dead" run-to-run. Re-run the checker for a fresh result.

## Sources

| Source | Channels | New after dedupe |
|--------|----------|------------------|
| Original hand-curated list | 151 | 151 |
| [iptv-org](https://github.com/iptv-org/iptv) — India (`countries/in`) | 715 | 629 |
| [iptv-org](https://github.com/iptv-org/iptv) — Hindi (`languages/hin`) | 324 | 25 |
| **Combined unique** | | **805** |

Deduplicated by URL (scheme + host + path, ignoring query strings).

## Results

| Bucket | Count | File |
|--------|-------|------|
| ✅ Active (verified live, HTTPS) | **512** | `india-active.m3u` |
| ⚠️ Unverifiable (`http://`, see note) | 189 | `india-unverifiable-http.m3u` |
| ❌ Dead / blocked (HTTPS, 4xx / errors) | 104 | — |

`india-active.m3u` is the **active-only** playlist. The `#EXTM3U x-tvg-url="…"`
EPG header is preserved.

## Why some links are "unverifiable" rather than active/dead

This check ran inside a sandbox whose outbound egress **only tunnels HTTPS**.
Plain-`http://` URLs (the IP-and-port streams) cannot be reached from here at
all, so they were **not** marked dead — they are set aside in
`india-unverifiable-http.m3u` for you to test on your own machine:

```bash
python -m m3u check playlists/india-unverifiable-http.m3u -o http-active.m3u -v
```

## Notes on the "dead" HTTPS links

Most failures are genuine `404`/`403`. Some `403`s are likely **geo-blocking**
— several channels reject requests from outside India — so they may well play
for you locally even though they failed from this server. Re-run the checker
from an Indian connection to confirm.

## Reproduce

```bash
cd tools/m3u
pip install -e ".[check]"
python -m m3u check ../../playlists/india.m3u -o ../../playlists/india-active.m3u -v
```
