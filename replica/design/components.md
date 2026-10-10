# Aura v2 components

Tokens: `tokens.json` → `tokens.css` (`python3 build_tokens.py`). Contrast: `python3 contrast.py tokens.json` (27 pairs, 0 AA failures).
Screen IDs (S01–S12) are from `../recon.md`. Icons: keep v1's own stroke SVGs (24px grid, 1.9–2px stroke, `currentColor`),
moved into one `icons.ts` sprite. The bloom logo is Aura's own, so it stays. Primitives are rendered in `primitives.html`
(screenshot: `screens/primitives.png`).

## Focus model (applies to every interactive component)

v1 fakes focus with `.sel` / `.kbf` classes on `<div>`s, and there are zero `:focus` styles. v2:

- Every interactive thing is a real `<button>` or `<a>`. The D-pad zone manager moves **real DOM focus** (roving `tabindex`: one `0` per zone, the rest `-1`).
- One focus style: `:focus-visible { outline: none; box-shadow: var(--shadow-focus-ring) }`. On TV (`html.tv`) also apply it on `:focus`, because remotes don't trigger focus-visible reliably.
- "Selected" (current tab, active nav) and "focused" are different states that can both be true at once, and both stay visible.
- `prefers-reduced-motion`: durations go to 0 (from tokens.css) and hover/press translates are removed.

---

```
NavRailButton
  variants  live, fav, guide, search, settings
  sizes     --nav-item (56 desktop / 72 tv / 48 mobile), icon 24 (32 tv)
  states    default (text-muted), hover (text, bg white/4%), active=current view (gradient-nav-active, text white,
            aria-current="page"), focus-visible (focus-ring), pressed
  tokens    radius 2xl(16→20 tv), motion fast
  a11y      <button aria-label="Live TV">. v1 relies on title only. Rail is <nav aria-label="Main">; ↑/↓ move within the rail, → enters content
  used on   S02, S06, S05, S09
```

```
ChannelCard
  variants  grid card, search result (compact)
  parts     number, logo (Logo), name (md/700, 1 line ellipsis), subline (programme now, else category; xs, text-muted),
            HD badge, favourite toggle, now-progress hairline
  states    default (gradient-card, border), hover (border-strong, translateY -2px), focus-visible (focus-ring),
            playing (playing-ring + "Playing" sr-only text), favourite on (heart filled, accent-3),
            needs-proxy-unavailable (hidden, not disabled), loading-EPG (subline = category, no shimmer)
  tokens    radius xl, padding space-4, gap space-3, min width --grid-min-card
  a11y      the card is a <button> (v1: <div>); accessible name "123, Star Plus HD, now: <programme>".
            The heart is a separate <button aria-pressed> **outside** the card button (no nested buttons) and is reached with → from the card on D-pad.
            G toggles favourite on the focused card
  used on   S02, S05
```

```
Logo (channel logo)
  variants  image, initials placeholder
  sizes     sm 40×30 (rows), md 64×48 (cards), lg 96×72 (hero; 120×90 tv)
  states    loading (initials shown underneath), loaded, error → initials (never a broken-image icon)
  tokens    bg surface-2, radius md, initials lg/800 text-muted
  a11y      alt="" (the channel name is always adjacent text)
  used on   S02, S03, S05, S07, S08, S10
```

```
Tab (category tab)
  variants  category, special (India ⭐ geo, DD Free Dish)
  states    default (text-muted), hover (text), selected (gradient-accent, on-accent, 700, glow-accent, aria-selected),
            focus-visible (focus-ring, also on selected), with count suffix
  tokens    base/600, padding 10/16, radius md
  a11y      role="tablist"/"tab" with aria-controls the grid; ←/→ move, Enter/OK selects (manual activation, so a remote doesn't refilter on every press)
  used on   S02
```

```
ToolbarButton (ghbtn)
  variants  icon+label (Search, Sort, HD only), menu trigger (Language, with caret)
  sizes     height --control-h (38), icon 16
  states    default (border-strong), hover (bg white/8%), on/toggled (border focus, bg info/18%, aria-pressed=true),
            focus-visible, pressed (translateY 1px), menu-open (aria-expanded=true)
  tokens    radius md, sm/600, gap space-2
  a11y      label hidden under 760px. Keep it as aria-label. Sort announces the new order via the Toast live region
  used on   S02
```

```
Menu (language)
  parts     options with label + count
  states    closed, open, option focused, option checked (aria-checked), empty-count option dimmed but selectable
  tokens    bg overlay, border border-strong, radius lg, shadow pop
  a11y      role="menu" + menuitemradio; ↑/↓ move, Enter selects, Esc closes and returns focus to the trigger, outside click closes
  used on   S04
```

```
Hero (NOW PLAYING)
  parts     eyebrow "NOW PLAYING" (2xs, letter-spaced), Logo lg, name (display), live dot + programme + category,
            LiveProgress, time range + "N min left", Badge row, Watch button, page dots, UpNext panel
  states    with EPG, without EPG (shows "Live", no progress), preview video (muted, 55% opacity) / static art,
            compact (<1100: UpNext hidden, name 30), mobile (<760: stacked, min-h auto)
  tokens    padding 34/40 (48/60 tv), min-h --hero-min-h, gap space-5
  a11y      region aria-label="Now playing"; progress has role="progressbar" with aria-valuetext "23 minutes left"
  used on   S03
```

```
Button (primary — "Watch now", "Start watching", "Save")
  variants  primary (gradient-accent), secondary (border-strong, transparent)
  sizes     md 44, lg 52 (tv ×1.3)
  states    default, hover (glow-accent stronger), pressed (translateY 1px), focus-visible, disabled (50% opacity, no glow), loading (spinner + label kept)
  tokens    radius lg, base/800, on-accent
  a11y      real <button>; loading sets aria-busy
  used on   S01, S03, S09
```

```
IconButton (player: back, mute, fullscreen, guide, retry, next)
  sizes     --control-h-player (40), icon 17
  states    default (bg white/6%), hover (white/10%), toggled (muted / fullscreen icons swap, aria-pressed), focus-visible
  tokens    radius md (11→10)
  a11y      aria-label always ("Mute", "Exit fullscreen"); keyboard M / F shortcuts listed in aria-keyshortcuts
  used on   S07
```

```
Badge
  variants  HD, audio, LIVE (live colour + dot), geo "India only" (warn)
  states    static
  tokens    2xs/700, padding 6/12, radius sm, border border-strong
  used on   S02, S03, S07
```

```
ProgressBar
  variants  boot (gradient, animated width), live programme (gradient fill on border track), player hairline
  states    0–100%, indeterminate (boot when no steps)
  tokens    height 4 (boot 6), radius pill, motion width 1s linear (live) / 250ms (boot)
  a11y      role="progressbar" + aria-valuenow, or aria-hidden when the same info is in adjacent text
  used on   S01, S03, S07
```

```
PlayerBar (OSD)
  parts     back IconButton, channel number (mono, 2xl), name (md), programme line + LiveProgress, volume group, fullscreen, guide
  states    shown, auto-hidden (after 3.5s idle while playing), pinned (just tuned / paused / error), YouTube mode (no volume)
  tokens    gradient from black/70% to transparent, padding 18/24
  a11y      any key or pointer move shows it. Hiding never removes focus from the focused control
  used on   S07
```

```
VolumeSlider
  states    0–1 step .05, muted (thumb at 0, icon swaps), focus-visible
  a11y      <input type="range" aria-label="Volume">; ↑/↓ change volume only when focused (otherwise they zap)
  used on   S07
```

```
StatusOverlay (player)
  variants  tuning (spinner + "Tuning <name>…"), tuning via proxy, buffering (small pill top-centre), no-signal (test pattern + Retry + Next channel)
  states    as variants; transitions fade
  tokens    text on overlay; no-signal title 2xl/800; buttons IconButton
  a11y      role="status" aria-live="polite" for tuning/buffering; no-signal moves focus to Retry
  used on   S07
```

```
SurfCard (channel banner on zap)
  parts     Logo md, number (2xl mono), name, now programme
  states    shown on zap / number entry, fades after 2.5s
  tokens    bg overlay 92%, radius xl, shadow pop
  a11y      announced via the shared live region ("124, Zee News")
  used on   S07
```

```
GuideListRow (in-player mini guide + TV list)
  parts     number, Logo sm, name, now programme, playing marker
  states    default, focused, current (live colour marker), playing
  a11y      list is role="listbox" with aria-activedescendant (one tab stop, fast on long lists); Enter switches
  used on   S08, S10
```

```
EpgGrid
  parts     DayTabs, time header (sticky), channel column (sticky), virtualized programme cells, now line
  cell states  past (text-dim), now (border focus, text), future, focused (focus-ring), too-narrow (title hidden, tooltip/sr label)
  tokens    px per minute constant, row height 56 (72 tv), cell radius sm
  a11y      role="grid": arrows move cell to cell (←/→ by programme, ↑/↓ by channel at the same time), Enter on a now cell tunes;
            cell label "Star Plus, 20:00 to 20:30, Anupamaa, on now"
  used on   S06
```

```
DayTabs
  states    default, selected (gradient-accent), focus-visible
  rule      days split at LOCAL midnight (see architecture "time zones")
  used on   S06
```

```
SearchField
  parts     magnifier icon, input, clear button
  states    empty (placeholder text-dim), typing, results, no results ("No channels match '…'" plus a hint to try the number), focus (border focus)
  tokens    height 52, radius lg, border border-input, bg surface
  a11y      role="combobox" + aria-controls results listbox; ↓ moves into results; Esc closes overlay and restores focus
  used on   S05, S09 (proxy URL uses the same field without results)
```

```
Modal (Help & settings)
  parts     title (xl), tag line, help rows (emoji/icon + text), proxy SearchField + Save, close
  states    open, closed, proxy saved (Toast), proxy invalid (inline danger text)
  tokens    bg overlay, border border-strong, radius 2xl, shadow pop, max-width 560
  a11y      <dialog> with showModal(): focus trap, Esc closes, focus returns to the rail button
  used on   S09
```

```
Toast
  states    shown, fading (motion fade)
  tokens    bg overlay 95%, border border-strong, radius md, sm/600, bottom 64 right 34
  a11y      one shared element with role="status" aria-live="polite" (v1 creates a <div> with no role, so screen readers never hear it)
  used on   all
```

```
Clock
  variants  rail (time + date stacked), TV bar (inline)
  a11y      aria-hidden (decorative; updating text would spam screen readers)
  used on   S02, S10
```

```
BootScreen
  parts     bloom logo (animated), ProgressBar boot, status line, Start button
  states    idle (Start focused), progressing, done (fade out), TV (skipped)
  a11y      Start button autofocus; progress status in role="status"
  used on   S01
```

```
TVHome (list mode)
  parts     top bar (buttons + clock), category column (GuideListRow-like), channel list (GuideListRow), preview pane (Logo lg, now/next)
  states    category focused, list focused, preview updating, empty category (skipped, never rendered)
  rule      no grid, no SVG animation, virtualized list
  used on   S10
```

```
DiagnosticsPanel
  states    shown with ?diag=1 only
  tokens    mono 2xs, bg overlay, text-muted
  used on   S11
```
