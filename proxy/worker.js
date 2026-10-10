/**
 * Aura CORS/HLS proxy — Cloudflare Worker.
 *
 * Makes free IPTV streams that don't send CORS headers playable in a browser by
 * re-serving them with `Access-Control-Allow-Origin: *`. For HLS it rewrites the
 * manifest so the variant playlists and media segments are fetched through the
 * proxy too (otherwise the browser would hit the origin CDN directly and be
 * blocked again).
 *
 * Usage from the page:  <worker-url>/?url=<url-encoded stream URL>
 *
 * Deploy: see proxy/README.md  (npx wrangler deploy, free tier).
 */

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,HEAD,OPTIONS",
  "Access-Control-Allow-Headers": "*",
  "Access-Control-Expose-Headers": "*",
};

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/125.0 Safari/537.36";

const M3U8_RE = /\.m3u8(\?|$)/i;

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    const here = new URL(request.url);

    // Device diagnostics sink: the app POSTs a small JSON report here; we forward
    // it to the repo as a repository_dispatch so a workflow can commit it under
    // logs/. No-op (silent) unless GH_LOG_TOKEN is configured on the Worker.
    if (here.pathname === "/log") {
      if (request.method !== "POST")
        return new Response("POST only", { status: 405, headers: CORS });
      const token = env && env.GH_LOG_TOKEN;
      let body = "";
      try { body = await request.text(); } catch {}
      if (!token) return new Response("", { status: 204, headers: CORS }); // not configured
      let payload;
      try { payload = JSON.parse(body); } catch { payload = { raw: String(body).slice(0, 4000) }; }
      try {
        const gh = await fetch("https://api.github.com/repos/gnaidu05/Iptv/dispatches", {
          method: "POST",
          headers: {
            Authorization: "Bearer " + token,
            Accept: "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "aura-proxy",
          },
          body: JSON.stringify({ event_type: "aura-log", client_payload: payload }),
        });
        return new Response("", { status: gh.ok ? 204 : 502, headers: CORS });
      } catch (e) {
        return new Response("", { status: 502, headers: CORS });
      }
    }

    const target = here.searchParams.get("url");
    if (!target) {
      return new Response("Aura proxy. Use /?url=<encoded stream url>", {
        status: 400,
        headers: { ...CORS, "Content-Type": "text/plain" },
      });
    }

    let upstreamUrl;
    try {
      upstreamUrl = new URL(target);
      if (!/^https?:$/.test(upstreamUrl.protocol)) throw new Error("scheme");
    } catch {
      return new Response("Bad url", { status: 400, headers: CORS });
    }

    const fwd = { "User-Agent": UA, Accept: "*/*" };
    const range = request.headers.get("Range");
    if (range) fwd["Range"] = range;
    // A referer/origin matching the stream host helps some CDNs.
    fwd["Referer"] = upstreamUrl.origin + "/";

    let resp;
    try {
      resp = await fetch(upstreamUrl.toString(), {
        headers: fwd,
        redirect: "follow",
        cf: { cacheTtl: 0 },
      });
    } catch (e) {
      return new Response("Upstream fetch failed: " + e, {
        status: 502,
        headers: CORS,
      });
    }

    const ct = resp.headers.get("Content-Type") || "";
    const isManifest =
      M3U8_RE.test(upstreamUrl.pathname) ||
      /mpegurl/i.test(ct) ||
      ct.includes("application/x-mpegURL");

    // Base used to rewrite child URLs back through this proxy.
    const self = here.origin;

    if (isManifest) {
      const text = await resp.text();
      // Only rewrite a genuine playlist. If the upstream failed (e.g. a geo
      // 403 returned as an HTML error page), pass the real status through so
      // the player sees the failure instead of a rewritten error page.
      const ok = resp.status >= 200 && resp.status < 300 && text.trimStart().startsWith("#EXTM3U");
      if (!ok) {
        return new Response(text, {
          status: resp.status && resp.status >= 400 ? resp.status : 502,
          headers: { ...CORS, "Content-Type": "text/plain", "Cache-Control": "no-store" },
        });
      }
      const out = rewriteManifest(text, upstreamUrl, self);
      return new Response(out, {
        status: 200,
        headers: {
          ...CORS,
          "Content-Type": "application/vnd.apple.mpegurl",
          "Cache-Control": "no-store",
        },
      });
    }

    // Segments / keys / anything else: stream straight through with CORS added.
    const headers = new Headers(CORS);
    for (const h of ["Content-Type", "Content-Length", "Accept-Ranges", "Content-Range"]) {
      const v = resp.headers.get(h);
      if (v) headers.set(h, v);
    }
    headers.set("Cache-Control", "no-store");
    return new Response(resp.body, { status: resp.status, headers });
  },
};

function proxied(absUrl, self) {
  return self + "/?url=" + encodeURIComponent(absUrl);
}

function rewriteManifest(text, baseUrl, self) {
  const lines = text.split(/\r?\n/);
  const out = [];
  for (let line of lines) {
    const t = line.trim();
    if (t === "") {
      out.push(line);
      continue;
    }
    if (t.startsWith("#")) {
      // Rewrite URI="..." attributes (EXT-X-KEY, EXT-X-MAP, EXT-X-MEDIA, …).
      line = line.replace(/URI="([^"]+)"/g, (m, uri) => {
        try {
          return 'URI="' + proxied(new URL(uri, baseUrl).toString(), self) + '"';
        } catch {
          return m;
        }
      });
      out.push(line);
      continue;
    }
    // A plain URI line: a variant playlist or a media segment.
    try {
      out.push(proxied(new URL(t, baseUrl).toString(), self));
    } catch {
      out.push(line);
    }
  }
  return out.join("\n");
}
