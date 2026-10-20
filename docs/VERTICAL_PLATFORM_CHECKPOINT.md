# Vertical platform work — paused at user request

Stable release remains 1.0.1. The earlier successful 1.0.2-rc.1 installer does not contain these new platform/canvas edits. Do not present this checkpoint as tested or release-ready.

## Last completed validation

Commit 024bdc092ccd1f1139e6fd96806339b783780ef1: 247 Python tests passed locally; Windows native module compiled and real horizontal/portrait RTMP encode/decode passed in run 39359845997. Browser QA failed at browser-qa.cjs:44 checking option.isDisabled(). Locally reproduced the actual option disabled/hidden flags with JSDOM; Playwright retargets a label-contained option to its select. The assertion now reads the actual disabled and hidden properties; this change has not yet passed browser CI.

## Unfinished edits in this checkpoint

- Native persistent FDGCast Vertical Studio canvas uses OBS frontend canvas registration, per-collection UUID storage, restore after loading/profile changes, video-output busy guards, and a private production portrait renderer. It is intended to appear under OBS Additional Canvas and preserve the main encoder.
- Companion setup card and bounded native telemetry/command bridge for enabling/disabling the canvas. OBS Enhanced Broadcasting and Additional Canvas selection remain explicit user settings.
- Portrait RTMP encoders can reuse the canvas render. Shared H.264/AAC compatibility encoders added for cases where Twitch Enhanced Broadcasting uses incompatible codecs; hardware-family selection and lifecycle need native validation.
- Direct portrait choices currently limited to YouTube, TikTok, Instagram and Vimeo. Twitch uses the canvas route; Kick and unverified routes are excluded.
- Encoded harness extended with a persistent canvas save/reload case and compatible encoder checks. Workflow copies the new headers.

## Resume here

1. Review all new native resource ownership, shutdown/profile/collection callbacks, compatibility encoder choices, and behavior with active encoders. No new native canvas code has compiled yet.
2. Add API tests for feature gating, busy/selected guards, sanitized telemetry, and command handling. Add browser checks for canvas setup states, destination filtering, and distinct YouTube presets.
3. Run focused checks, then one Windows build with browser and encoded canvas QA. Fix failures before delivering any installer. Consider a distinct rc.2 version to avoid confusing the older successful rc.1 artifact.
4. Real Twitch Enhanced Broadcasting/Additional Canvas selection and platform playback remain operator checks. No account credentials or real broadcasts were used.
5. Update the draft PR and review notes after validation. Do not publish a stable release automatically.

## Sources reviewed

- Twitch dual format: https://help.twitch.tv/s/article/dual-format-vertical-video — Enhanced Broadcasting and Additional Canvas, rather than another ordinary stream key.
- YouTube: https://support.google.com/youtube/answer/2474026 — custom vertical Encoder feed uses a second key within one broadcast.
- TikTok official regional OBS guide: https://seller-uk.tiktok.com/university/essay?default_language=en&knowledge_id=7738055662569218 — portrait 9:16 plus account-provided RTMP URL/key. Does not prove universal encoder access or a fixed follower threshold.
- TikTok LIVE Studio portrait documentation: https://www.tiktok.com/live/studio/help/article/Enhance-visuals/Use-dual-layout-to-go-LIVE-in-portrait-and-landscape-simultaneously?lang=en
- Vimeo: https://help.vimeo.com/hc/en-us/articles/40727149468305-About-4K-Streaming — external encoder vertical formats documented; live-plan access required. No real Vimeo broadcast tested.
- Instagram original Meta Live Producer page was inaccessible; official Streamlabs integration documentation describes 9:16 RTMP and Live Producer access. Current Meta account eligibility still needs dashboard confirmation: https://support.streamlabs.com/hc/en-us/articles/19796470357787-How-to-stream-to-Instagram
- Kick documentation gives standard output recommendations up to 1920x1080; no verified dual-format ingest found: https://help.kick.com/en/articles/7066931-how-to-stream-on-kick-com
- OBS 32.2.2 source: frontend/settings/OBSBasicSettings_Stream.cpp, frontend/OBSStudioAPI.cpp, libobs/obs-canvas.c. Persistent frontend canvases enter Additional Canvas; EPHEMERAL canvases are excluded.
