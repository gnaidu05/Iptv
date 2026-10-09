package tv.aura.app;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
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

    /** URL to load — adds &tv=1 on a TV so the web app switches to its 10-foot,
     *  fully D-pad-navigable layout instead of the phone/browser layout. */
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

    // HTML5 fullscreen video state
    private View customView;
    private WebChromeClient.CustomViewCallback customViewCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
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
        });

        web.setWebChromeClient(new FullscreenChromeClient());

        // Android TV: the WebView must hold focus so the remote's D-pad reaches
        // the page as arrow-key events (the web app handles arrow/Enter/Back nav).
        web.setFocusable(true);
        web.setFocusableInTouchMode(true);

        root.addView(web);
        setContentView(root);
        web.requestFocus();

        // Always load the live page fresh. Restoring a saved WebView state across
        // a process death (common on TV, where the launcher kills backgrounded
        // apps) could come back as a blank/black screen, and a fresh load also
        // picks up the latest channel list. Broad configChanges in the manifest
        // keep rotation/resize from recreating the Activity, so nothing is lost.
        web.loadUrl(appUrl());
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
            c.setReadTimeout(15000);
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
            return new WebResourceResponse(mime, enc, code, reason, headers, body);
        } catch (Exception e) {
            return null;
        }
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

    /** Handle HTML5 fullscreen video by swapping the WebView for the video view. */
    private class FullscreenChromeClient extends WebChromeClient {
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
