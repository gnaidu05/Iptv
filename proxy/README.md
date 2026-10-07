# Aura CORS/HLS proxy

A handful of Aura's channels (~37) come from servers that don't send CORS
headers. Browsers refuse to play those directly, so in the web app they're
hidden by default and show up only once you point Aura at a small proxy that
re-serves the stream **with** CORS.

`worker.js` is that proxy — a single [Cloudflare Worker](https://workers.cloudflare.com/)
(free tier). It adds `Access-Control-Allow-Origin: *` and, for HLS, rewrites the
manifest so the variant playlists and video segments are fetched through the
proxy too.

> The **Android app** does not need this — it adds CORS natively, so all
> channels already play there.

## Deploy (≈2 minutes, free)

You need a free Cloudflare account. Pick whichever is easiest:

### Option A — one click (recommended)

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/gnaidu05/Iptv/tree/main/proxy)

Opens Cloudflare, asks you to authorize in your own browser, and deploys this
`proxy/` folder to your account. When it finishes it shows the
`https://…workers.dev` URL.

### Option B — GitHub Action (I can trigger it for you)

1. Create an API token at <https://dash.cloudflare.com/profile/api-tokens> with
   the **“Edit Cloudflare Workers”** template.
2. In this repo: **Settings → Secrets and variables → Actions → New repository
   secret**, name it `CLOUDFLARE_API_TOKEN`, paste the token. (If your login has
   more than one Cloudflare account, add `CLOUDFLARE_ACCOUNT_ID` too.)
3. Run the **“Deploy CORS proxy”** workflow (Actions tab → Run workflow) — or
   just tell me and I'll trigger it. The `…workers.dev` URL prints in the log.

### Option C — command line

```bash
cd proxy
npx wrangler login       # opens your browser to authorize (one time)
npx wrangler deploy      # prints a URL like https://aura-proxy.<you>.workers.dev
```

## Turn it on in Aura

Open the web app, tap the **gear / Help** button, paste the Worker URL into
**“Play extra channels”**, and **Save**. Aura reloads and the extra channels
appear and play. (You can also pass it once via `?proxy=https://…workers.dev`.)

To turn it off, clear the field and Save.

## Test it

```
https://aura-proxy.<you>.workers.dev/?url=https%3A%2F%2Fexample.com%2Fstream.m3u8
```

should return a playlist whose lines point back at your worker.

## Notes & limits

- Free Workers allow ~100,000 requests/day. HLS pulls many small segment
  requests, so that's roughly a few hours of viewing per day — fine for personal
  use. Heavy use may need the paid plan.
- The proxy only relays what you ask it to; it carries the same free FTA/FAST
  streams Aura already lists. It does **not** bypass geo-blocks — the India ⭐
  channels still need an Indian connection.
- Run your own instance; don't expose it publicly as an open proxy.
