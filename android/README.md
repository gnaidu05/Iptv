# Aura for Android (phone + TV)

A lightweight **WebView shell** that wraps the hosted Aura web app
(`https://gnaidu05.github.io/Iptv/webstb/`) in a native Android app — so it
installs like any app, runs full-screen, plays HLS, and supports HTML5
fullscreen video. Because it loads the live site, the channel list and the
weekly auto-refresh keep working with no app update needed.

The **same APK runs on phones and on Android TV / Fire TV / Google TV** — it
declares the leanback launcher + a TV banner, and the remote's D-pad drives the
grid (arrows to move, OK to play, Back to go up a level). On a TV box, sideload
`aura.apk` (e.g. via *Downloader* / *Send files to TV* / `adb install`) and it
appears in the TV home screen's apps row.

## Get the APK

The [**Build Android APK**](../../actions/workflows/android.yml) GitHub Action
builds it on every change to `android/` and attaches `aura.apk` to the
[`apk-latest` release](../../releases/tag/apk-latest). Download it there, or
from the workflow run's **Artifacts**.

Direct link once the first build has run:

```
https://github.com/gnaidu05/Iptv/releases/download/apk-latest/aura.apk
```

## Install on your phone

1. Download `aura.apk` to the phone.
2. Open it; Android will ask to allow **Install unknown apps** for your browser
   or file manager — enable it, then tap **Install**.
3. It's a debug-signed build, so Play Protect may warn — choose *Install anyway*.

## Build locally

Needs JDK 17 and the Android SDK (platform 34, build-tools 34).

```bash
cd android
./gradlew assembleDebug
# → app/build/outputs/apk/debug/app-debug.apk
```

## Notes

- `minSdk 21` (Android 5.0+), `targetSdk 34` — runs on virtually every Android
  phone and TV in use. No AndroidX — just the framework `WebView`, so the build
  is small and fast.

### Diagnostics / logs

The app mirrors the web page's console and a device/timing report to logcat and
to a local file, and (if configured) uploads them to the repo:

- **logcat:** `adb logcat -s AuraDiag AuraWeb` while the app runs.
- **local file:** `aura-log.txt` in the app's external files dir
  (`/sdcard/Android/data/tv.aura.app/files/aura-log.txt`) — pull with
  `adb pull` or a file manager.
- **to the repo:** the page POSTs a small JSON report to the proxy's `/log`
  endpoint, which forwards it to the repo (committed under `logs/`) when the
  Worker has a `GH_LOG_TOKEN` secret set — see `proxy/README.md`.
- Add `?diag=1` to the URL to show an on-screen diagnostics panel.
- HTTPS-only (`usesCleartextTraffic="false"`); the app plays the same
  browser-safe streams as the web STB.
- To ship a Play Store build, replace the debug signing with a release keystore
  and switch the workflow to `assembleRelease` (or a TWA via Bubblewrap).
