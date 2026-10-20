# FDGCast 1.0.2-rc.2 — vertical platform setup test build

This is a review candidate. Stable updates remain on 1.0.1.

- Twitch: enable the FDGCast canvas in Vertical Studio, then choose it in OBS Settings → Stream → Enhanced Broadcasting → Additional Canvas. Uses the existing Twitch connection; no second key. The main output encoder is never replaced.
- YouTube: distinct Horizontal and Vertical presets select the starting picture format and explain the two keys. For dual format, choose Encoder in YouTube's vertical preview and send the second key from its own destination.
- TikTok: portrait output requires an account-provided encoder server URL and stream key. LIVE Studio access or connecting username-based chat does not establish encoder access.
- Instagram: portrait output requires eligible Live Producer access and its current session credentials. Vimeo requires an eligible live-event plan. Check each platform's preview and publishing step.
- Kick and unverified portrait ingest routes are excluded from the vertical destination picker. Existing unsupported portrait choices must be repaired before starting; keys remain saved.
- Studio RTMP outputs can reuse the registered portrait canvas. Compatible H.264/AAC encoders are shared when the main codecs cannot be reused; this can add encoding load. OBS manages Twitch Enhanced Broadcasting's own encoders and bandwidth.

Close OBS and Companion before installing. Test using Twitch Inspector bandwidth-test mode and a private YouTube broadcast before the next public stream. Platform eligibility and actual viewer playback still need operator verification.
