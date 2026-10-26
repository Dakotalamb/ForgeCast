# FDGCast 1.0.2 — output recovery and vertical streaming

- Twitch horizontal + vertical uses OBS Enhanced Broadcasting and the FDGCast Additional Canvas, with no second Twitch key. Setup now explains the minimum four video tracks for two canvases.
- Separate YouTube Horizontal and YouTube Vertical presets clarify picture selection and stream keys. TikTok, Instagram and Vimeo portrait setup explains required encoder access. Unverified portrait routes, including Kick, are excluded from the vertical picker.
- Output health reports increasing bytes and actual dimensions, distinguishing sending, stalled and reconnecting outputs. Separate horizontal and portrait outputs preserve independent credentials.
- OBS retains control of the main encoder. Portrait outputs reuse the canvas where possible, with compatible H.264/AAC fallbacks and renderer recursion protection.

Close OBS and Companion before installing. Save layouts in Vertical Studio, enable its Twitch canvas, then select it in OBS Settings → Stream → Additional Canvas with Enhanced Broadcasting enabled. Set Maximum Video Tracks to at least 4. Extra encodes and uploads require GPU and bandwidth headroom; four tracks may still exceed a particular system's available encoder capacity.

Validation: the candidate passed 249 regression tests, four Chromium UI suites, real OBS canvas save/restart checks, simultaneous landscape/portrait video and audio encoding, and Windows installer checks. The operator subsequently reported streaming working after resolving the track-count setup. The stable package reruns these automated gates before publication. This does not establish live playback on every platform or hardware configuration.

Facebook/Instagram chat still requires the separate configured Hub and platform approval. TikTok chat remains experimental; platform credentials and eligibility are required. Paid overlay entitlements are unchanged.

See [vertical platform setup](VERTICAL-PLATFORM-SETUP.md) for platform-specific instructions.
