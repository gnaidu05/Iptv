# Aura for Android

A lightweight **WebView shell** that wraps the hosted Aura web app
(`https://gnaidu05.github.io/Iptv/webstb/`) in a native Android app — so it
installs like any app, runs full-screen, plays HLS, and supports HTML5
fullscreen video. Because it loads the live site, the channel list and the
weekly auto-refresh keep working with no app update needed.

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

- `minSdk 26` (Android 8.0+), `targetSdk 34`. No AndroidX — just the framework
  `WebView`, so the build is small and fast.
- HTTPS-only (`usesCleartextTraffic="false"`); the app plays the same
  browser-safe streams as the web STB.
- To ship a Play Store build, replace the debug signing with a release keystore
  and switch the workflow to `assembleRelease` (or a TWA via Bubblewrap).
