# India playlist — link check report

Generated with `python -m m3u check` against `examples/india.m3u`
(151 channels total). Each stream URL was fetched and, for HLS endpoints,
verified to return HTTP 200 with a valid `#EXTM3U` manifest.

> **Point-in-time snapshot.** Live IPTV streams flap; a couple of channels
> move between "active" and "dead" run-to-run. Re-run the checker for a fresh
> result.

## Results

| Bucket                                   | Count | File                              |
|------------------------------------------|-------|-----------------------------------|
| ✅ Active (verified live, HTTPS)         | 101   | `india-active.m3u`                |
| ⚠️ Unverifiable (`http://`, see note)    | 24    | `india-unverifiable-http.m3u`     |
| ❌ Dead / blocked (HTTPS, 4xx / errors)  | 26    | —                                 |

`india-active.m3u` is the requested **active-only** playlist. The original
`#EXTM3U x-tvg-url="…"` EPG header is preserved.

## Why some links are "unverifiable" rather than active/dead

This check ran inside a sandbox whose outbound egress **only tunnels HTTPS**.
Plain-`http://` URLs (the IP-and-port streams such as
`http://103.72.101.252:8080/…`) cannot be reached from here at all, so they
were **not** marked dead — they are set aside in
`india-unverifiable-http.m3u` for you to test on your own machine:

```bash
python -m m3u check examples/india-unverifiable-http.m3u -o http-active.m3u -v
```

## Notes on the "dead" HTTPS links

Most failures are genuine `404`/`403`. Some `403`s are likely **geo-blocking**
— several channels (e.g. `*.aynaott.com`, the `keralive.workers.dev` Asianet
feeds) reject requests from outside India. Those may well play for you locally
even though they failed from this server. Re-run the checker from an Indian
connection to confirm.

## Reproduce

```bash
cd m3u
pip install -e ".[check]"
python -m m3u check examples/india.m3u -o examples/india-active.m3u -v
```
