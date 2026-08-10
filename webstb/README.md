# STB — a set-top box in the browser

A smart-TV–style set-top box that boots, scans the channel database, shows a
grid launcher with a **NOW PLAYING** hero and real **now / next** EPG, and
**plays the selected channel** via HLS — driven by
`playlists/india-active.m3u`.

## Features

- **Boot sequence** — firmware/SoC init, network, channel scan, guide load.
- **Grid launcher** with a left navigation rail (Live / Favourites / Guide /
  Search / Settings), live clock, date and network status.
- **NOW PLAYING hero** — logo, name, **current programme + time range**, a
  real progress bar with "N min left", HD / audio badges, and a **UP NEXT**
  schedule panel.
- **Channel cards** — number, logo, name, the **programme airing now**
  (falls back to category), HD badge, and a per-card favourite toggle.
- **Category tabs** built from the real channel groups.
- **Search, Sort, Filter (HD-only), Favourites** — via the colour-coded action
  bar or keyboard.
- **Fullscreen player** with a channel info bar and a **"No Signal"
  test-pattern** fallback for streams the browser can't play.
- Favourites, last-channel and watch history saved in `localStorage`.

## Controls

| Key | Action |
|-----|--------|
| `↑ ↓ ← →` | Move focus around the channel grid |
| `Enter` | Play the focused channel (fullscreen) |
| `Esc` / `Back` | Leave the player / close overlay |
| `← →` (in player) | Zap to previous / next channel |
| `0`–`9` | Direct channel-number entry |
| `R` | Search · `G` Favourites · `Y` Sort · `B` Filter |
| `/` | Search |

Everything is also clickable — the rail icons, tabs, cards, hearts, the
colour-coded action bar, and the player controls.

## Now / next EPG

Real programme data comes from `epg.json`, a compact guide built from the
community-maintained **Tata Play** and **JioTV** XMLTV feeds
([mitthu786/tvepg](https://github.com/mitthu786/tvepg)), matched to our
channels by name (~300 of the lineup covered; the rest show a live indicator).
The STB computes now/next client-side from absolute timestamps, so the guide
stays correct between refreshes. Rebuild locally with:

```bash
python scripts/build_epg.py
```

## Run it

```bash
cd webstb
python -m http.server 8080     # then open http://localhost:8080
```

Live (auto-deployed): **https://gnaidu05.github.io/Iptv/webstb/**

## Playback notes

- Uses [`hls.js`](https://github.com/video-dev/hls.js) on MSE browsers and
  native HLS on Safari.
- Browser playback is subject to **CORS**. CDN-backed channels
  (Akamai / CloudFront / Amagi) generally send `Access-Control-Allow-Origin: *`
  and play; some origin servers don't and show **No Signal** — that's the
  server, not the box.
- The STB playlist is HTTPS-only (mixed content blocks `http://` on the
  `https://` page); verified `http://` channels live in
  `../playlists/india-active-http.m3u` for native players.

## Auto-refresh

- A [weekly Action](../.github/workflows/refresh.yml) re-checks every stream,
  prunes dead ones, and regenerates `channels.js`.
- An [EPG Action](../.github/workflows/epg.yml) rebuilds `epg.json` every
  6 hours so now/next stays current.

Both redeploy this page automatically.
