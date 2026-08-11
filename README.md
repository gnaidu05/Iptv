# Iptv

Curated IPTV playlists with a small tool to keep them healthy.

Every stream in the **active** playlist has been fetched and verified to return
a valid HLS (`#EXTM3U`) manifest. A [weekly GitHub Action](.github/workflows/refresh.yml)
re-runs the health check, prunes dead streams, pulls in new ones, and
redeploys the web set-top box — so the lists stay fresh automatically.

## 📺 Live playlist links

Paste into VLC (**File → Open Network Stream**) or any IPTV player:

**India — active channels (verified live):**

```
https://raw.githubusercontent.com/gnaidu05/iptv/main/playlists/india-active.m3u
```

| Playlist | File |
|----------|------|
| India — active, **HTTPS** (browser + player safe) | [`playlists/india-active.m3u`](playlists/india-active.m3u) |
| India — active, **HTTP** (native players like VLC) | [`playlists/india-active-http.m3u`](playlists/india-active-http.m3u) |
| India — full source list | [`playlists/india.m3u`](playlists/india.m3u) |
| Samsung TV Plus — India (⚠️ India-only) | [`playlists/samsung-india.m3u`](playlists/samsung-india.m3u) |

Channels are aggregated from a hand-curated list plus the
[iptv-org](https://github.com/iptv-org/iptv) India (`in`) and Hindi, Tamil,
Telugu, Bengali & Malayalam free-to-air collections, deduplicated by URL, and
re-verified weekly. See [`playlists/CHECK_REPORT.md`](playlists/CHECK_REPORT.md)
for the current counts and notes on geo-blocking.

> `india-active.m3u` is HTTPS-only so it plays from the `https://` web STB;
> `http://` streams can't (mixed content), so verified-working ones live in
> `india-active-http.m3u` for native players.
>
> `samsung-india.m3u` is a **separate, unverified** list of Samsung TV Plus'
> 200 free India channels. These streams are **geo-locked to India** and
> ad-session based — they won't play in the hosted web STB and are kept out of
> the health-check pipeline. Load it in a native player (VLC / TV app) from
> India. Regenerate with `python scripts/build_samsung_india.py`.

## 🖥️ Aura — web TV app

A smart-TV–style browser live-TV app — boots, scans the lineup, shows a grid
launcher with a NOW PLAYING hero, real **now / next EPG**, and plays the
selected channel via HLS. Live at:

```
https://gnaidu05.github.io/Iptv/webstb/
```

Or run locally: `cd webstb && python -m http.server 8080`. Now/next comes from
the Tata Play + JioTV + epgshare01 guides (~350 channels, rebuilt every 6h into
`webstb/epg.json`). Full controls and playback notes in
[`webstb/README.md`](webstb/README.md).

## Tool: `m3u`

A small, dependency-free Python library + CLI for parsing, writing, and
**health-checking** M3U / M3U8 playlists. Lives in
[`tools/m3u`](tools/m3u).

```bash
cd tools/m3u
pip install -e ".[check]"

# Probe every stream and emit only the active channels
python -m m3u check ../../playlists/india.m3u -o ../../playlists/india-active.m3u -v

# Other commands
python -m m3u info ../../playlists/india-active.m3u
python -m m3u ls   ../../playlists/india-active.m3u
```

The checker honours `#EXTVLCOPT` hints (`http-referrer`, `http-user-agent`,
`http-origin`) and preserves the `#EXTM3U` header (e.g. `x-tvg-url` for EPG).
Full tool docs: [`tools/m3u/README.md`](tools/m3u/README.md).

## License

MIT — see [`tools/m3u`](tools/m3u) for the packaged tool.
