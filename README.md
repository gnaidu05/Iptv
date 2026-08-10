# Iptv

Curated IPTV playlists with a small tool to keep them healthy.

Every stream in the **active** playlist has been fetched and verified to return
a valid HLS (`#EXTM3U`) manifest. Live streams flap, so treat each list as a
point-in-time snapshot and re-run the checker to refresh.

## 📺 Live playlist links

Paste into VLC (**File → Open Network Stream**) or any IPTV player:

**India — active channels (verified live):**

```
https://raw.githubusercontent.com/gnaidu05/iptv/main/playlists/india-active.m3u
```

| Playlist | Channels | File |
|----------|----------|------|
| India — active (verified live, HTTPS) | 536 | [`playlists/india-active.m3u`](playlists/india-active.m3u) |
| India — full source list | 893 | [`playlists/india.m3u`](playlists/india.m3u) |
| India — `http://` streams (test locally) | 196 | [`playlists/india-unverifiable-http.m3u`](playlists/india-unverifiable-http.m3u) |

Channels are aggregated from a hand-curated list plus the
[iptv-org](https://github.com/iptv-org/iptv) India (`in`) and Hindi, Tamil,
Telugu, Bengali & Malayalam free-to-air collections, deduplicated by URL. See
[`playlists/CHECK_REPORT.md`](playlists/CHECK_REPORT.md) for the full
active / dead / unverifiable breakdown and notes on geo-blocking.

## 🖥️ Web set-top box

A browser set-top box that boots, scans the channel list, and plays the
selected channel via HLS — see [`webstb/`](webstb). Enable GitHub Pages
(Settings → Pages → *Deploy from a branch* → `main` / root) and it goes live at
`https://gnaidu05.github.io/Iptv/webstb/`, or run it locally:

```bash
cd webstb && python -m http.server 8080   # then open http://localhost:8080
```

Boot → live TV with OSD banner → EPG-style channel list → on-screen remote.
Full controls and playback notes in [`webstb/README.md`](webstb/README.md).

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
