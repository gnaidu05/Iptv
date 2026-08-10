# m3u

A small, dependency-free Python library and CLI for parsing and writing
**M3U / M3U8** playlists — including the extended `#EXTM3U` form with `#EXTINF`
metadata and IPTV attributes such as `tvg-id` and `group-title`.

## Install

```bash
cd m3u
pip install -e .
```

Requires Python 3.8+. No runtime dependencies.

## Library usage

```python
from m3u import Playlist

# Parse an existing playlist
playlist = Playlist.parse_file("playlist.m3u")
for track in playlist:
    print(track.duration, track.title, track.path)

print("Total:", playlist.total_duration, "seconds")

# Build one from scratch
pl = Playlist()
pl.append("song.mp3", title="A Song", duration=210)
pl.append("http://example.com/stream", title="Live", duration=-1,
          **{"tvg-id": "ch1", "group-title": "News"})

pl.write_file("out.m3u")            # extended #EXTM3U form
print(pl.dumps(extended=False))     # plain path-per-line form
```

### Model

| Object      | Notable members                                                          |
|-------------|--------------------------------------------------------------------------|
| `Track`     | `path`, `title`, `duration`, `attributes`, `is_stream`                    |
| `Playlist`  | `append()`, `extend()`, `remove()`, `total_duration`, `dumps()`, `write_file()`, iteration & indexing |

## Command line

```bash
# Summary statistics
python -m m3u info playlist.m3u

# List tracks with index and duration
python -m m3u ls playlist.m3u

# Build a playlist from paths (stdout, or -o FILE)
python -m m3u build song1.mp3 song2.mp3 -o out.m3u

# Plain output, no #EXTINF metadata
python -m m3u build a.mp3 b.mp3 --simple

# Probe every stream and emit only the ACTIVE channels
python -m m3u check channels.m3u -o active.m3u -v
```

### Checking live streams

`m3u check` fetches each entry, and for HLS (`.m3u8`) endpoints confirms the
response is a real `#EXTM3U` manifest before counting it active. It honours
`#EXTVLCOPT` hints (`http-referrer`, `http-user-agent`, `http-origin`) and
preserves the `#EXTM3U` header (e.g. `x-tvg-url`) on the output. This needs the
optional `requests` dependency:

```bash
pip install -e ".[check]"
python -m m3u check channels.m3u -o active.m3u --workers 30 --timeout 12 -v
```

Options: `-o/--output`, `-t/--timeout` (seconds), `-w/--workers` (concurrency),
`-v/--verbose` (report every result, not just failures). Note that a checker
can only report what it can *reach*: geo-blocked streams and plain-`http://`
URLs behind an HTTPS-only network will show as unreachable from that host.

After `pip install -e .` the `m3u` console script is available directly
(`m3u info playlist.m3u`).

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT — see the repository `LICENSE`.
