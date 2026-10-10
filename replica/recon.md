# Recon map: Aura (web STB + Android/Android TV WebView shell)

Scope: the whole product. It is small enough: boot → channel launcher → live
playback, plus the EPG, search/filter, favourites, the TV-box list mode, and
the pipeline that keeps the lineup alive (health check, EPG build, CORS proxy).
For: the repo owner. The map documents Aura so it can be rebuilt or re-platformed
(for example native Android TV, Tizen/webOS or a framework rewrite) at feature parity.
Date: 2026-10-10

> Recon of the user's **own** codebase, so the source code is a legitimate
> source here. No third-party app was examined. `replica/screens/` is empty.
> Grab reference screenshots from the live site before you start a rebuild.

## Sources

| # | source | URL | notes |
| --- | --- | --- | --- |
| 1 | web app (live) | https://gnaidu05.github.io/Iptv/webstb/ | the real thing; `?tv=1` TV list mode, `?app=1` play-all, `?diag=1` diagnostics, `?proxy=` override |
| 2 | web app source | `webstb/index.html` (1850 lines, single file) | every screen, keymap, localStorage key |
| 3 | web app docs | `webstb/README.md` | feature list + controls table |
| 4 | channel data | `webstb/channels.js` (built by `webstb/build.py`) | 868 channels; `num,name,url,logo,group,tvgId,lang` (+ `px`, `geo`, `fd`, `yt`, `ytlive`) |
| 5 | EPG data | `webstb/epg.json` (`scripts/build_epg.py`) | 456 channels, `[start,end,title]` tuples, ~33h window |
| 6 | Android shell | `android/app/.../MainActivity.java`, `android/README.md` | WebView, D-pad → key events, native CORS, diagnostics bridge |
| 7 | CORS proxy | `proxy/worker.js`, `proxy/README.md` | Cloudflare Worker; HLS manifest rewrite; `/log` ingest |
| 8 | pipeline | `.github/workflows/*.yml`, `scripts/refresh.py`, `tools/m3u` | weekly health check, 6-hourly EPG, Pages deploy, APK build |
| 9 | health report | `playlists/CHECK_REPORT.md` | 1647 source → 792 HTTPS active → 758 browser-playable, 74 geo |

## Core loop

Open the app, pick a free Indian live channel from a TV-style grid (it shows what's on now), and it plays in fullscreen. Channel up/down zaps like a real set-top box.

## Screens

| ID | screen | route / how to reach | purpose | key components | states seen |
| --- | --- | --- | --- | --- | --- |
| S01 | Boot | app launch (`#boot`) | power-on splash, cosmetic init sequence | logo bloom, progress bar, status text, "Start watching" button | idle (power button), progressing, skipped on TV |
| S02 | Launcher / Live grid | after boot, rail "Live" (`#main`) | browse and pick a channel | nav rail, clock/date, favourites pill, avatar, hero, category tabs, grid header tools, channel card grid | filled, empty filter result, EPG loading (category fallback), favourites view, HD-only, language-filtered |
| S03 | Hero (on S02) | top of S02 | NOW PLAYING: last/selected channel with now/next | logo, name, live dot, programme + progress bar, "N min left", badges, Watch now, dots, Recently Watched panel | no EPG (shows "Live"), no recents (empty copy), muted hero video |
| S04 | Language menu | S02 grid header → Language | filter by language, with counts | dropdown menu, options + counts | open/closed, keyboard focus |
| S05 | Search | rail Search, `/` or `R` (`#search`) | find a channel by name | text input, results card list | empty query, results, no results |
| S06 | Full TV guide (EPG) | rail Guide (`#epg`) | timeline grid of programmes | day tabs, time header, sticky channel column, virtualized programme cells, now line, "Updated N ago" | loading toast, no data toast, filled |
| S07 | Player | Enter/click a channel (`#player`) | fullscreen live playback | video, info bar (back, number, name, mute, volume, fullscreen, guide), programme progress, channel surf card, buffering spinner | tuning, playing, buffering, no signal (Retry / Next channel), YouTube embed, bar auto-hidden |
| S08 | In-player mini guide | player ↑/↓ (desktop), Enter or G (`#pguide`) | switch channel without leaving the player | current channel header (now/next), scrollable channel list | open/closed, selection |
| S09 | Help & settings | rail gear (`#help`) | how-to plus proxy URL setting | help rows, proxy input + Save, "Got it" | proxy empty / set |
| S10 | TV home (list mode) | `?tv=1` or Android TV (`#tvhome`) | lightweight STB list for weak boxes | top bar with buttons + clock, category column, channel list, preview pane | rows: Recently watched, Favourites, categories, DD Free Dish, India ⭐ geo |
| S11 | Diagnostics overlay | `?diag=1` | on-screen device/timing report | text panel | n/a |
| S12 | Toast (global) | any action | transient feedback ("Sorted by…", "Channel 123") | toast | show/fade |

## Flows

```
F01 Watch a channel (core loop)
    S01 -> S02 (focus card) -> S07 playing
    happy path clicks: 2 (Start watching, card). Last channel is preselected in the hero, so Watch now also works.
    edge: stream has no CORS (px) -> proxy retry -> No Signal; geo channel outside India; http stream (excluded);
          YouTube-sourced channel (iframe path); autoplay blocked until a user gesture

F02 Zap channels while watching
    S07 -> ←/→ (or ↑/↓ on TV) -> S07 next channel with surf card
    happy path clicks: 1 per zap
    edge: zapping past the end wraps around; a failed channel offers "Next channel"

F03 Direct channel-number entry
    S02/S07 -> digits 0-9 -> toast "Channel N" -> S07
    happy path keys: 1-4 digits
    edge: number does not exist

F04 Find by name
    S02 -> S05 type -> Enter/click result -> S07
    happy path clicks: 3
    edge: no results

F05 Browse by category / language / HD / sort
    S02 -> tab | S04 option | HD only | Sort (number → name → favourites)
    edge: combination yields 0 channels; geo channels appear only in the India ⭐ tab

F06 Favourite a channel and come back to it
    S02 heart on card (or G) -> rail Favourites / pill -> filtered grid
    edge: no favourites yet

F07 Check what's on later
    S02 -> rail Guide -> S06 scroll timeline / pick day
    edge: EPG not loaded yet; channel has no EPG (~47% of lineup)

F08 Switch channel from the in-player guide
    S07 -> S08 ↑/↓ -> Enter -> S07 new channel
    happy path keys: 3+

F09 Enable extra channels with a custom proxy
    S09 -> paste Worker URL -> Save -> reload -> px channels playable
    edge: invalid URL; clearing it turns the proxy off

F10 TV-box browsing (D-pad only)
    S10 category ↕ -> list ↕ (preview updates) -> OK -> S07 -> Back -> S10
    edge: Back key mapping via the Android shell

F11 (ops) Weekly lineup refresh
    cron -> refresh.py health check -> playlists + channels.js -> EPG rebuild -> Pages deploy
F12 (ops) 6-hourly EPG rebuild -> epg.json -> deploy
F13 (ops) Device log -> proxy /log -> log-ingest workflow -> logs/*.json
```

## Components

| component | variants | states | used on |
| --- | --- | --- | --- |
| Nav rail button | live, fav, guide, search, settings | default, active, keyboard focus (.kbf) | S02 |
| Channel card | grid card, search result | default, selected/focused, favourite on, HD badge, programme vs category subline, logo vs initials fallback | S02, S05 |
| Channel logo | img, initials placeholder | loaded, failed → initials | S02, S03, S05, S07, S08, S10 |
| Category tab | per group + ALL + India ⭐ (+ DD Free Dish) | default, active, kbf, with count | S02 |
| Toolbar button (ghbtn) | Search, Sort, Language (menu), HD only | default, on, kbf | S02 |
| Dropdown menu | language | open, closed, option focus | S04 |
| Hero | — | EPG/no-EPG, progress, badges | S03 |
| Progress bar | hero live bar, player progress, boot bar | 0-100% | S01, S03, S07 |
| Player bar | — | shown, auto-hidden, pinned | S07 |
| Icon button (pbtn) | back, mute, fullscreen, guide, retry, next | default, toggled (muted / fs) | S07 |
| Volume slider | — | 0-1, muted | S07 |
| Status overlay | spinner "Tuning…", buffering, No Signal test-pattern | — | S07 |
| Surf card | — | shown on zap, then fades | S07 |
| Guide list row | — | current, selected | S08 |
| EPG cell | programme block | past, now, future | S06 |
| Day tabs | — | active | S06 |
| Modal card | help | open/closed | S09 |
| Text input | search, proxy URL | empty, filled | S05, S09 |
| Toast | — | show, fade | all |
| TV list row / preview pane | — | selected | S10 |
| Clock/date | rail, TV bar | ticking | S02, S10 |

## Inferred data model

No backend: static JSON plus per-device localStorage.

```
Channel    num (int, stable display number), name, url (HLS m3u8), logo, group (";"-separated categories),
           tvgId, lang, px? (needs CORS proxy), geo? (India-only), fd? (DD Free Dish), yt?/ytlive? (YouTube source)
           evidence: channels.js, extras.json, build.py      confidence: high
Programme  channel_num, start (epoch s), end (epoch s), title
           evidence: epg.json {generated, window:[lo,hi], channels:{num:[[s,e,t],...]}}   confidence: high
Category   derived from Channel.group via catOf() + CAT_ORDER     confidence: high
Language   Channel.lang; menu order LANG_ORDER (14 values)          confidence: high
DeviceState (localStorage)
           stb_favs [num], stb_hist [num] (recently watched), stb_last num, stb_vol float, stb_muted '0'|'1',
           aura_proxy url
           evidence: index.html lines 748-1839                       confidence: high
DiagReport tag, device info, timings, console lines -> proxy /log -> logs/aura-*.json   confidence: high
Playlist   (pipeline) source pool -> active-https / web (CORS-verified) / active-http / geo buckets
           evidence: CHECK_REPORT.md, scripts/refresh.py              confidence: high
```

Relationships: Channel 1-n Programme (by num, matched by name at build time), Channel n-1 Category, Channel n-1 Language,
DeviceState n-n Channel (favourites, history).

## Feature matrix

See `features.csv`. Must: 17, should: 17, could: 8, skip: 3.

## Out of scope (cannot or should not be cloned)

- **The streams themselves.** They are third-party broadcasters' content. A rebuild consumes the same public playlists and owns none of the content.
- **EPG source feeds** (Tata Play, JioTV via mitthu786/tvepg, epgshare01). Those are external data, so a rebuild reuses the build script and doesn't recreate the data.
- **Samsung TV Plus India list.** It's geo-locked and ad-session based, and it already sits outside the app pipeline.
- **Geo-blocked playback verification.** It can't be verified from non-Indian CI, which is why it's tracked as unverified.

## Size

Screens 12 (10 real + diag + toast), flows 10 user + 3 ops, entities 5 (+ device state). Hard parts:

1. **Playback reliability across browsers and WebViews.** hls.js vs native HLS, CORS fallback through the proxy, tune timeouts, No Signal handling, the WebView cache/reload loop (see recent commits).
2. **D-pad / remote focus management.** There are zones (rail, tabs, tools, language menu, grid, list, player, mini guide, EPG), plus TV list mode for weak boxes.
3. **EPG.** Fuzzy name matching at build time and a virtualized multi-day timeline at runtime, across 868 channels.

Size: **M** (a few weeks) for a parity rebuild on a new framework/platform. The pipeline (refresh, EPG, proxy) can be reused as is, which keeps it from being L.
