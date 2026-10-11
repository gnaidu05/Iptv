package tv.aura.app;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.TextView;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.Map;

/**
 * Aura — a thin WebView shell around the hosted web app
 * (https://gnaidu05.github.io/Iptv/webstb/). It keeps the live channel list and
 * weekly refreshes working, enables HLS playback, and supports HTML5 fullscreen
 * video so the in-app fullscreen button behaves like a native player.
 *
 * It loads the page with ?app=1 (so the web app surfaces the channels a plain
 * browser can't play) and intercepts cross-origin requests to add CORS headers,
 * so those non-CORS streams play natively — no proxy needed.
 */
public class MainActivity extends Activity {

    private static final String APP_URL = "https://gnaidu05.github.io/Iptv/webstb/?app=1";
    private static final String HOST = "gnaidu05.github.io";
    private static final String LOG_URL = "https://aura-proxy.gnaidu05.workers.dev/log";

    private long createdAt = 0;
    private volatile boolean loggedThisLaunch = false;

    private void showStatus(String msg) {
        if (status == null) return;
        status.setText("Aura v" + appVersionName() + "\n" + msg);
        status.setVisibility(View.VISIBLE);
    }

    private void hideStatus() {
        if (status != null) status.setVisibility(View.GONE);
    }

    /** The page is on screen: clear the loading overlay and stop the watchdog. */
    private void markLoaded(WebView view) {
        if (pageFinished) return;
        pageFinished = true; reloadTries = 0;
        ui.removeCallbacks(watchdog);
        hideStatus();
        // Force the WebView to recomposite its surface — some TV panels show a
        // black WebView until something triggers a redraw.
        if (view != null) {
            final WebView w = view;
            w.postInvalidate();
            w.setVisibility(View.GONE);
            ui.post(new Runnable() { @Override public void run() { if (w != null) w.setVisibility(View.VISIBLE); } });
        }
        long loadMs = (createdAt > 0) ? (android.os.SystemClock.elapsedRealtime() - createdAt) : -1;
        postDeviceLog(loadMs);
    }

    /** Post a device report to the log endpoint ourselves, so a diagnostics
     *  record reaches the repo even if the page's own JS is stale or blocked.
     *  Fire-and-forget on a background thread; silent no-op if logging is off. */
    private void postDeviceLog(final long loadMs) {
        if (loggedThisLaunch) return;
        loggedThisLaunch = true;
        final boolean tv = isTelevision();
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    String wv = "?";
                    try {
                        android.content.pm.PackageInfo pi = WebView.getCurrentWebViewPackage();
                        if (pi != null) wv = pi.packageName + " " + pi.versionName;
                    } catch (Throwable ignored) { }
                    String json = "{"
                        + "\"tag\":\"android\""
                        + ",\"ts\":\"" + jsonEsc(new java.util.Date().toString()) + "\""
                        + ",\"device\":\"" + jsonEsc(android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL) + "\""
                        + ",\"androidSdk\":" + android.os.Build.VERSION.SDK_INT
                        + ",\"tv\":" + tv
                        + ",\"webview\":\"" + jsonEsc(wv) + "\""
                        + ",\"appVersion\":\"" + jsonEsc(appVersionName()) + "\""
                        + ",\"loadMs\":" + loadMs
                        + ",\"paintVia\":\"" + paintVia + "\""
                        + ",\"reloads\":" + reloadTries
                        + ",\"starts\":" + startedCount
                        + ",\"maxProgress\":" + maxProgress
                        + ",\"tStarted\":" + tStarted
                        + ",\"tFirstProgress\":" + tFirstProgress
                        + ",\"tCommit\":" + tCommit
                        + ",\"tFinished\":" + tFinished
                        + "}";
                    HttpURLConnection c = (HttpURLConnection) new URL(LOG_URL).openConnection();
                    c.setConnectTimeout(10000);
                    c.setReadTimeout(10000);
                    c.setRequestMethod("POST");
                    c.setDoOutput(true);
                    c.setRequestProperty("Content-Type", "application/json");
                    c.getOutputStream().write(json.getBytes("UTF-8"));
                    c.getOutputStream().close();
                    int code = c.getResponseCode();
                    appendLog("AuraDiag", "device log posted (http " + code + "): " + json);
                    c.disconnect();
                } catch (Exception e) {
                    appendLog("AuraDiag", "device log post failed: " + e);
                }
            }
        }).start();
    }

    private static String jsonEsc(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ").replace("\r", " ");
    }

    private String appVersionName() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception e) { return "?"; }
    }

    /** Main-frame load failed or hung: show a message and reload with backoff,
     *  which recovers the common cold-launch case where Wi-Fi isn't up yet. */
    private void retryLoad(String msg) {
        ui.removeCallbacks(watchdog);
        if (web == null) return;
        if (reloadTries < 6) {
            reloadTries++;
            showStatus(msg);
            long delay = Math.min(8000L, 1000L * reloadTries);
            ui.postDelayed(new Runnable() {
                @Override public void run() {
                    if (!pageFinished && web != null) { hadError = false; web.loadUrl(appUrl()); }
                }
            }, delay);
        } else {
            showStatus("Can't reach Aura.\nCheck this TV's internet connection, then reopen the app.");
        }
    }

    /** URL to load — adds &tv=1 on a TV so the web app switches to its 10-foot,
     *  fully D-pad-navigable layout instead of the phone/browser layout. Uses
     *  normal HTTP caching (no per-launch cache-buster): re-downloading the page
     *  and channel list every launch made cold start very slow on TV boxes; the
     *  app updates on revalidation instead. */
    private String appUrl() {
        return isTelevision() ? APP_URL + "&tv=1" : APP_URL;
    }

    /** True on Android TV / Fire TV / Google TV (leanback / TV ui-mode). */
    private boolean isTelevision() {
        try {
            android.app.UiModeManager um =
                    (android.app.UiModeManager) getSystemService(UI_MODE_SERVICE);
            if (um != null && um.getCurrentModeType()
                    == android.content.res.Configuration.UI_MODE_TYPE_TELEVISION) {
                return true;
            }
        } catch (Exception ignored) { }
        return getPackageManager().hasSystemFeature("android.software.leanback");
    }
    private static final String UA =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    + "(KHTML, like Gecko) Chrome/125.0 Safari/537.36";

    private WebView web;
    private FrameLayout root;

    // Load resilience: on a cold TV launch the network is often not up yet, so
    // the first page fetch fails and the WebView shows a black screen. We show a
    // native loading/error overlay and auto-retry the main-frame load.
    private final Handler ui = new Handler(Looper.getMainLooper());
    private TextView status;
    private int reloadTries = 0;
    private boolean pageFinished = false;
    private boolean hadError = false;
    // Load timeline instrumentation (all offsets in ms from createdAt).
    private int startedCount = 0, maxProgress = 0;
    private long tStarted = 0, tFirstProgress = 0, tCommit = 0, tFinished = 0;
    private String paintVia = "none";
    private final Runnable watchdog = new Runnable() {
        @Override public void run() {
            // Only reload if the page truly never started loading — reloading a
            // slow-but-progressing load just restarts it and makes things worse.
            if (!pageFinished && maxProgress < 10) retryLoad("Still connecting…");
        }
    };
    private long since() { return createdAt > 0 ? android.os.SystemClock.elapsedRealtime() - createdAt : -1; }

    // HTML5 fullscreen video state
    private View customView;
    private WebChromeClient.CustomViewCallback customViewCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        createdAt = android.os.SystemClock.elapsedRealtime();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#05070e"));
        root.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        web = new WebView(this);
        web.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        web.setBackgroundColor(Color.parseColor("#05070e"));

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                // Keep in-app navigation inside the WebView.
                view.loadUrl(url);
                return true;
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                return proxyIfNeeded(req);
            }

            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                pageFinished = false; hadError = false;
                startedCount++;
                if (tStarted == 0) tStarted = since();
                showStatus("Loading Aura…");
                ui.removeCallbacks(watchdog);
                ui.postDelayed(watchdog, 25000);   // only reloads if progress stays <10%
            }

            @Override
            public void onPageCommitVisible(WebView view, String url) {
                // First real paint — the app is on screen. This is the success
                // signal, NOT onPageFinished (whose load event waits for every
                // sub-resource and can lag minutes on a TV).
                if (tCommit == 0) tCommit = since();
                if ("none".equals(paintVia)) paintVia = "commit";
                markLoaded(view);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (tFinished == 0) tFinished = since();
                if (!hadError) { if ("none".equals(paintVia)) paintVia = "finished"; markLoaded(view); }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, android.webkit.WebResourceError err) {
                if (!pageFinished && req != null && req.isForMainFrame()) { hadError = true; retryLoad("Couldn't connect — retrying…"); }
            }

            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest req, WebResourceResponse resp) {
                if (!pageFinished && req != null && req.isForMainFrame()) { hadError = true; retryLoad("Couldn't connect — retrying…"); }
            }

            // Pre-API-23 devices (Android 5.0/5.1) get the deprecated callback;
            // only the main document URL triggers a retry.
            @Override
            @SuppressWarnings("deprecation")
            public void onReceivedError(WebView view, int errorCode, String desc, String failingUrl) {
                if (!pageFinished && failingUrl != null && failingUrl.contains("/Iptv/webstb")) {
                    hadError = true; retryLoad("Couldn't connect — retrying…");
                }
            }
        });

        web.setWebChromeClient(new FullscreenChromeClient());

        // Diagnostics bridge: the web app reports device/timing info and errors
        // here; we mirror them to logcat (adb logcat -s AuraDiag AuraWeb) and to a
        // local log file, so sluggishness/black-screen reports can be investigated.
        web.addJavascriptInterface(new DiagBridge(), "AuraShell");

        // Android TV: the WebView must hold focus so the remote's D-pad reaches
        // the page as arrow-key events (the web app handles arrow/Enter/Back nav).
        web.setFocusable(true);
        web.setFocusableInTouchMode(true);

        root.addView(web);

        // Native loading/error overlay over the dark background (so a slow or
        // failed load is never just a black screen). The version is shown large
        // so the running build is verifiable on screen.
        status = new TextView(this);
        status.setText("Aura v" + appVersionName() + "\nLoading…");
        status.setTextColor(Color.parseColor("#e7ecf5"));
        status.setTextSize(26);
        status.setGravity(Gravity.CENTER);
        status.setPadding(60, 40, 60, 40);
        FrameLayout.LayoutParams slp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        slp.gravity = Gravity.CENTER;
        root.addView(status, slp);

        setContentView(root);
        web.requestFocus();

        // After an app update, clear the WebView cache ONCE so the new build
        // always loads the latest page (a plain install-over otherwise keeps the
        // old cached HTML). Normal launches keep their cache, so they stay fast.
        clearCacheOnUpdate();

        // Always load the live page fresh. Restoring a saved WebView state across
        // a process death (common on TV, where the launcher kills backgrounded
        // apps) could come back as a blank/black screen, and a fresh load also
        // picks up the latest channel list. Broad configChanges in the manifest
        // keep rotation/resize from recreating the Activity, so nothing is lost.
        web.loadUrl(appUrl());

        // Guarantee a device report even if the page never paints (hangs
        // mid-load): if nothing has reported within 6s, send a snapshot of the
        // load state so the timeline is captured regardless of outcome.
        ui.postDelayed(new Runnable() {
            @Override public void run() { if (!loggedThisLaunch) postDeviceLog(-1); }
        }, 6000);

        // Stall recovery: if the page still hasn't painted after 35s, reload it
        // once (even if it was slowly progressing) so it can't hang forever. Capped
        // so it never becomes the old tight reload loop.
        ui.postDelayed(new Runnable() {
            @Override public void run() {
                if (!pageFinished && web != null && reloadTries < 2) {
                    reloadTries++; hadError = false;
                    showStatus("Taking a while — retrying once…");
                    web.loadUrl(appUrl());
                }
            }
        }, 35000);
    }

    private void clearCacheOnUpdate() {
        try {
            android.content.SharedPreferences sp = getSharedPreferences("aura", MODE_PRIVATE);
            int last = sp.getInt("lastVer", -1);
            int cur = getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
            if (last != cur) {
                web.clearCache(true);
                sp.edit().putInt("lastVer", cur).apply();
                appendLog("AuraDiag", "cleared WebView cache on update " + last + "->" + cur);
            }
        } catch (Exception ignored) { }
    }

    /**
     * Re-fetch cross-origin requests natively and return them with CORS headers,
     * so streams whose servers omit Access-Control-Allow-Origin still play. The
     * app's own assets (same host) are left to the WebView. Returns null on any
     * problem, falling back to default handling.
     */
    private WebResourceResponse proxyIfNeeded(WebResourceRequest req) {
        try {
            android.net.Uri u = req.getUrl();
            String host = u.getHost();
            String scheme = u.getScheme();
            if (host == null || host.equalsIgnoreCase(HOST)) return null;   // app assets
            if (scheme == null || !(scheme.equals("http") || scheme.equals("https"))) return null;
            if (isPassthrough(host)) return null;   // let the WebView handle YouTube/Google natively
            if (isImage(u.getPath())) return null;  // logos/images aren't CORS-gated; fetch natively (faster, parallel)

            String method = req.getMethod();
            if ("OPTIONS".equalsIgnoreCase(method)) {
                return new WebResourceResponse(
                        "text/plain", "utf-8", 204, "No Content", corsHeaders(),
                        new java.io.ByteArrayInputStream(new byte[0]));
            }
            if (!"GET".equalsIgnoreCase(method)) return null;

            HttpURLConnection c = (HttpURLConnection) new URL(u.toString()).openConnection();
            c.setInstanceFollowRedirects(true);
            c.setConnectTimeout(12000);
            c.setReadTimeout(20000);
            c.setRequestMethod("GET");
            c.setRequestProperty("User-Agent", UA);
            c.setRequestProperty("Accept", "*/*");
            c.setRequestProperty("Referer", scheme + "://" + host + "/");
            Map<String, String> rh = req.getRequestHeaders();
            if (rh != null && rh.get("Range") != null) c.setRequestProperty("Range", rh.get("Range"));
            c.connect();

            int code = c.getResponseCode();
            String reason = c.getResponseMessage();
            if (reason == null || reason.isEmpty()) reason = "OK";

            String ctype = c.getContentType();
            String mime = "application/octet-stream";
            String enc = null;
            if (ctype != null) {
                int sc = ctype.indexOf(';');
                mime = (sc > 0 ? ctype.substring(0, sc) : ctype).trim();
                int ci = ctype.toLowerCase().indexOf("charset=");
                if (ci >= 0) enc = ctype.substring(ci + 8).trim();
            }

            Map<String, String> headers = corsHeaders();
            copyHeader(c, headers, "Accept-Ranges");
            copyHeader(c, headers, "Content-Range");
            copyHeader(c, headers, "Content-Length");
            headers.put("Cache-Control", "no-store");

            InputStream body = (code >= 400) ? c.getErrorStream() : c.getInputStream();
            if (body == null) body = new java.io.ByteArrayInputStream(new byte[0]);
            // Buffer so the WebView reads segments in large chunks, not byte-by-byte.
            return new WebResourceResponse(mime, enc, code, reason, headers,
                    new java.io.BufferedInputStream(body, 64 * 1024));
        } catch (Exception e) {
            return null;
        }
    }

    /** Static image assets (channel logos) — not subject to CORS, so let the
     *  WebView fetch them directly instead of re-routing through our proxy. */
    private static boolean isImage(String path) {
        if (path == null) return false;
        String p = path.toLowerCase();
        return p.endsWith(".png") || p.endsWith(".jpg") || p.endsWith(".jpeg")
                || p.endsWith(".webp") || p.endsWith(".gif") || p.endsWith(".svg")
                || p.endsWith(".ico") || p.endsWith(".bmp");
    }

    /** Hosts that must use the WebView's own networking (cookies, auth) rather
     * than our CORS re-fetch — chiefly the YouTube embed player and its CDN. */
    private static boolean isPassthrough(String host) {
        host = host.toLowerCase();
        String[] skip = {"youtube.com", "youtube-nocookie.com", "googlevideo.com",
                "ytimg.com", "ggpht.com", "google.com", "gstatic.com", "googleapis.com",
                "doubleclick.net", "googlesyndication.com"};
        for (String s : skip) {
            if (host.equals(s) || host.endsWith("." + s)) return true;
        }
        return false;
    }

    private static Map<String, String> corsHeaders() {
        Map<String, String> h = new HashMap<>();
        h.put("Access-Control-Allow-Origin", "*");
        h.put("Access-Control-Allow-Methods", "GET,HEAD,OPTIONS");
        h.put("Access-Control-Allow-Headers", "*");
        h.put("Access-Control-Expose-Headers", "*");
        return h;
    }

    private static void copyHeader(HttpURLConnection c, Map<String, String> into, String name) {
        String v = c.getHeaderField(name);
        if (v != null) into.put(name, v);
    }

    /** Device/runtime facts the web diagnostics can't see, prepended to reports. */
    private String deviceInfo() {
        String wv = "?";
        try {
            android.content.pm.PackageInfo pi = WebView.getCurrentWebViewPackage();
            if (pi != null) wv = pi.packageName + " " + pi.versionName;
        } catch (Throwable ignored) { }
        return "device=" + android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL
                + "; androidSdk=" + android.os.Build.VERSION.SDK_INT
                + "; tv=" + isTelevision() + "; webview=" + wv;
    }

    /** Append a line to logcat and a capped local log file (adb pull, or a file
     *  manager, can retrieve it from the app's external files dir). */
    private void appendLog(String tag, String line) {
        Log.i(tag, line);
        try {
            java.io.File dir = getExternalFilesDir(null);
            if (dir == null) return;
            java.io.File f = new java.io.File(dir, "aura-log.txt");
            if (f.length() > 256 * 1024) f.delete();   // keep it small
            java.io.FileWriter w = new java.io.FileWriter(f, true);
            w.write(System.currentTimeMillis() + " [" + tag + "] " + line + "\n");
            w.close();
        } catch (Exception ignored) { }
    }

    /** Exposed to the page as window.AuraShell — the web app reports here. */
    private class DiagBridge {
        @android.webkit.JavascriptInterface
        public void diag(String json) { appendLog("AuraDiag", deviceInfo() + "; " + json); }
        @android.webkit.JavascriptInterface
        public void log(String msg) { appendLog("AuraWeb", msg); }
        @android.webkit.JavascriptInterface
        public String info() { return deviceInfo(); }
    }

    /** Handle HTML5 fullscreen video by swapping the WebView for the video view. */
    private class FullscreenChromeClient extends WebChromeClient {
        @Override
        public boolean onConsoleMessage(android.webkit.ConsoleMessage m) {
            if (m != null) appendLog("AuraWeb", m.messageLevel() + " " + m.message()
                    + " @" + m.lineNumber());
            return true;
        }

        @Override
        public void onProgressChanged(WebView view, int newProgress) {
            if (newProgress > 0 && tFirstProgress == 0) tFirstProgress = since();
            if (newProgress > maxProgress) maxProgress = newProgress;
            // The page is actually downloading/parsing — don't let the watchdog
            // reload it (reloading a slow-but-working load only makes it slower).
            if (newProgress >= 10 && !pageFinished) ui.removeCallbacks(watchdog);
            if (newProgress >= 100) { if ("none".equals(paintVia)) paintVia = "progress"; markLoaded(view); }
        }

        @Override
        public void onShowCustomView(View view, CustomViewCallback callback) {
            if (customView != null) {
                callback.onCustomViewHidden();
                return;
            }
            customView = view;
            customViewCallback = callback;
            web.setVisibility(View.GONE);
            root.addView(customView, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            enterImmersive();
        }

        @Override
        public void onHideCustomView() {
            if (customView == null) return;
            root.removeView(customView);
            customView = null;
            customViewCallback.onCustomViewHidden();
            web.setVisibility(View.VISIBLE);
            exitImmersive();
        }
    }

    private void enterImmersive() {
        View d = getWindow().getDecorView();
        d.setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
    }

    private void exitImmersive() {
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_VISIBLE);
    }

    /**
     * Drive the web app with the TV remote's D-pad. WebView does not reliably
     * deliver D-pad arrow/OK presses to the page's JS key handlers (which is why
     * the boot screen could get stuck and the grid wouldn't move), so we map them
     * to the arrow/Enter keys the web app listens for and inject them directly,
     * consuming the native event to avoid double navigation. Back is left to the
     * framework so onBackPressed() runs. Non-D-pad keys fall through unchanged.
     */
    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (web != null && customView == null && event.getAction() == KeyEvent.ACTION_DOWN) {
            String key = null;
            switch (event.getKeyCode()) {
                case KeyEvent.KEYCODE_DPAD_UP:    key = "ArrowUp"; break;
                case KeyEvent.KEYCODE_DPAD_DOWN:  key = "ArrowDown"; break;
                case KeyEvent.KEYCODE_DPAD_LEFT:  key = "ArrowLeft"; break;
                case KeyEvent.KEYCODE_DPAD_RIGHT: key = "ArrowRight"; break;
                case KeyEvent.KEYCODE_DPAD_CENTER:
                case KeyEvent.KEYCODE_ENTER:
                case KeyEvent.KEYCODE_NUMPAD_ENTER: key = "Enter"; break;
                default: break;
            }
            if (key != null) {
                injectKey(key);
                return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }

    /** Dispatch a synthetic keydown to the page so its remote-nav handlers run. */
    private void injectKey(String key) {
        final String js = "(function(k){try{document.dispatchEvent("
                + "new KeyboardEvent('keydown',{key:k,bubbles:true,cancelable:true}))}"
                + "catch(e){}})('" + key + "');";
        web.evaluateJavascript(js, null);
    }

    @Override
    public void onBackPressed() {
        if (customView != null) {
            web.getWebChromeClient().onHideCustomView();
            return;
        }
        // Ask the web app to close one UI layer (player, guide, search…). It
        // returns "true" if it handled Back; otherwise we fall back to native.
        web.evaluateJavascript("(window.auraBack&&window.auraBack())?true:false", value -> {
            if (!"true".equals(value)) {
                runOnUiThread(() -> {
                    if (web.canGoBack()) {
                        web.goBack();
                    } else {
                        finish();
                    }
                });
            }
        });
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    protected void onPause() {
        super.onPause();
        web.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
