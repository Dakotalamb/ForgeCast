# Verification record — September 28, 2026

Environment: Linux, Python 3.12.14, aiohttp 3.13.5, Node 24.19.0.

## Passed

- 52 automated Python tests (`python3 -m unittest discover -s tests -q`).
- Python source compilation (`python3 -m compileall -q launcher.py forgecast`).
- JavaScript syntax validation (`node --check web/app.js`).
- Aiohttp application startup/cleanup and local HTTP security tests.
- Mock OBS WebSocket authentication, event delivery, request routing, failure and
  disconnect behavior.
- Independent OBS auth hash verification using Node's crypto implementation.

Tests cover shared origin labels, relayed-message deduplication, removal handling,
bounded histories, YouTube normalization, rendering/network/encoding counter
deltas, reset behavior, diagnostic cooldown, destination validation, secret
exclusion, local API authentication, Origin/Host rejection, command confirmation,
native queue expiry, Hub HTTPS enforcement and adapter request construction.

## Not completed / blocked

- `node tests/browser-qa.cjs` launched the local demo server but could not launch
  Chromium because the Playwright browser binary is absent. No screenshot or
  rendered layout verification is claimed. The QA script is included for rerun.
- Native C++ module was not compiled: no CMake, OBS SDK or Qt6 SDK available here.
- No real Windows OBS launch, native DLL load/unload, GPU/encoder/network output
  tests or Windows DPAPI round-trip test.
- No live Twitch/YouTube OAuth, Shared Chat or RTMP broadcast tests. Account
  credentials were not available and no public streams/messages were sent.
- The Hub API and Google OAuth changes still need a deployed end-to-end check.

Automated local success does not establish live production readiness. Follow
`docs/NATIVE_BUILD.md` before installing the native module in a live OBS setup.
