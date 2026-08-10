# NOVA Web STB — a set-top box in the browser

A faithful web simulation of a set-top box that boots, scans the channel
database, shows an EPG-style channel list, and **plays the selected channel**
via HLS — driven by the `playlists/india-active.m3u` playlist.

![boot → live → guide → remote](.)

## Features

- **Boot sequence** — firmware/SoC init, network, channel scan, EPG load.
- **Live TV** with an on-screen OSD info banner (channel number, logo, name,
  category, LIVE indicator, clock) that auto-hides like a real box.
- **Channel list / guide** — category sidebar with live counts, numbered
  channels with logos, current-channel marker, favourites.
- **On-screen remote** + full keyboard control.
- **Direct channel entry** — type a number to tune.
- **Favourites** (starred, saved in `localStorage`) and a Favourites category.
- **Volume / mute, fullscreen, last-channel memory.**
- **"No Signal" test-pattern** fallback when a stream can't be played.

## Controls

| Remote | Keyboard | Action |
|--------|----------|--------|
| CH ▲ / CH ▼ | `↑` / `↓` | Zap to next / previous channel |
| OK | `Enter` | Open channel list · select highlighted channel |
| ◀ / ▶ | `←` / `→` | Volume − / + (in guide: change category) |
| GUIDE | `G` | Open / close the channel list |
| INFO | `i` / `Space` | Toggle the info banner |
| FAV | `F` | Favourite the current / highlighted channel |
| MUTE | `M` | Mute / unmute |
| 0–9 | `0`–`9` | Direct channel number entry |
| BACK | `Esc` | Close overlay |
| — | `R` | Toggle the on-screen remote |

## Run it

**Locally** (any static server — the page loads `channels.js` alongside it):

```bash
cd webstb
python -m http.server 8080
# open http://localhost:8080
```

**GitHub Pages** — enable Pages for this repo (Settings → Pages → *Deploy from
a branch* → `main` / root). The box is then live at:

```
https://gnaidu05.github.io/Iptv/webstb/
```

## Playback notes

- Uses [`hls.js`](https://github.com/video-dev/hls.js) (loaded from a CDN) for
  MSE browsers, and native HLS on Safari.
- Browser playback is subject to **CORS**. CDN-backed channels
  (Akamai / CloudFront / Amagi) generally send `Access-Control-Allow-Origin: *`
  and play; some origin servers don't and will show **No Signal** — that's the
  server, not the box. Zap to the next channel.
- `http://` streams won't play on an `https://` page (mixed content); the
  STB's playlist (`india-active.m3u`) is HTTPS-only so this is a non-issue here.
  Verified-working `http://` channels live in `../playlists/india-active-http.m3u`
  for native players.

## Auto-refresh

A [weekly GitHub Action](../.github/workflows/refresh.yml) re-checks every
stream, prunes dead ones, regenerates `channels.js`, and redeploys this page —
so the box stays current without manual work.

## Refresh the channel list

After re-running the health check and updating
`playlists/india-active.m3u`, regenerate the embedded database:

```bash
python webstb/build.py
```
