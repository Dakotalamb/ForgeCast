# Output recovery review — 1.0.2-rc.1

Isolated review candidate on next/output-recovery. It does not publish a release,
change the stable update feed, deploy the Hub or modify a running OBS instance.

## Changes

- Transport status uses byte progress: Waiting for data, Sending data, No data,
  Reconnecting, Stopping, Offline or Error. Five seconds without progress is
  stalled; a counter reset, reconnect or telemetry gap requires new evidence.
  Sending bytes is not proof of platform publication or viewer playback.
- Both OBS main and additional outputs report their real encoder dimensions and
  rate. OBS picture reuses whatever resolution OBS actually has; it does not
  force landscape. Old-module/missing telemetry is labelled unavailable.
- Adding a separate output in the other format preserves the original (in either direction), never copies its key,
  and asks for another supported broadcast connection. Duplicate saved ingest/key
  combinations are rejected; the native start also protects OBS main's connection.
  Both selected outputs can start together. One RTMP output still sends one format;
  platform support and separate broadcast setup remain required.
- Whole-picture mode explains the letterboxing produced by placing a wide scene
  inside a portrait frame and then inside a wide platform player. Fill crops sides;
  Studio provides independent framing. No automatic destructive scene transforms.
- The internal portrait helper is hidden from normal input selection and a shared
  thread-local guard prevents program/portrait recursion. Existing captures are
  reused; no GPU performance reduction is claimed.
- Main-output Vertical Studio routing remains disabled. OBS keeps its main
  encoder, service, audio and recording behavior. It will not be re-enabled based
  on a mocked preview or geometry-only test.

## Real encoded-output verification

The Windows workflow builds a libobs test executable using the production
portrait-rendering and encoder code. It runs against the checksum-verified
OBS 32.2.2 runtime, with synthetic color sources and an audible 440 Hz tone.
FFmpeg receivers bind only to localhost and capture simultaneous landscape and
portrait RTMP streams. Decoded H.264/AAC files are checked for exact dimensions,
fit/fill/camera colors and audible tone. Two start/stop cycles with different
scenes check source following and reuse. No creator accounts or public streams
are used. Logs and encoded fixtures are retained as workflow evidence.

This checks the renderer, encoder and transport against real libobs. It does not
exercise the OBS frontend's main-stream override (disabled), platform API access,
public-platform playback, physical GPU headroom, hardware encoders or real network
outages. A failed runtime check blocks this review build; it is not a passing
screenshot test and must not be waived silently.

## Acceptance

Review the workflow result and encoded evidence before installing after the live
stream. Then verify real viewer playback with the creator's existing settings.
There is no automated install, service change or restart.


## Validated review build

- Tested source: `5ef62197bd921598e7cde60c71279e66b6510776`.
- Successful Windows run: https://github.com/Dakotalamb/ForgeCast/actions/runs/39351413564
- 246 Python tests, native geometry/recursion checks, all four browser suites,
  packaged service/desktop and installed module checks passed.
- Real OBS 32.2.2 sent and decoded 12 localhost H.264/AAC captures: simultaneous
  1920 × 1080 landscape and 720 × 1280 portrait in fit/fill/Studio, with audible
  tone and changed scenes/layouts across stop/restart.
- Installer: `FDGCast-1.0.2-rc.1-win-x64-setup.exe` (22,749,306 bytes).
- SHA-256: `a159d8643d238b00c1f994310a9b03ca8374be0f520693299e854ca19ab63fa9`.
- Draft review: https://github.com/Dakotalamb/ForgeCast/pull/2
- Stable GitHub release remains v1.0.1; this work did not publish a release or
  deploy the Hub updater feed. Main-output vertical routing is still disabled.
