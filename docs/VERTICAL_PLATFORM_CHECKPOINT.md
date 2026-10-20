# Vertical platform work — validated review candidate

FDGCast 1.0.2-rc.2 is ready for operator testing. Stable release and automatic updates remain on 1.0.1. Close OBS and Companion before installing.

## Build receipt

- Tested source: abcf14a78f5790afcb27e00ceaea6ecfd50f2854
- Successful Windows run: https://github.com/Dakotalamb/ForgeCast/actions/runs/39446310646
- Installer: FDGCast-1.0.2-rc.2-win-x64-setup.exe
- Size: 22765941 bytes
- SHA-256: 72928de3562e24bd507eda4e6a85103b372ac2c67dca54902dac751e2f494dbe

## Validation completed

- 249 Python regression tests passed locally and on Windows, including canvas feature gating, safe setup-command queuing, busy/selected guards and bounded telemetry.
- Native geometry/render guards and Windows module compilation passed.
- Real libobs encoded simultaneous 1920x1080 landscape and 720x1280 portrait H.264/AAC streams into local RTMP receivers. Sixteen recordings covered fit, fill, Studio and shared canvas modes, with framing/audio decoding and two stop/start cycles per mode. Scene/layout changes happened between cycles, not during an active broadcast.
- A test-only module in the actual portable OBS 32.2.2 frontend registered exactly one persistent canvas. Its identity and Additional Canvas profile selection survived restart. Selected-canvas removal was blocked and main video dimensions were preserved. Evidence: artifacts/12276481948 in the successful run.
- Four Chromium suites passed, including separate YouTube presets, the Kick portrait restriction, Twitch setup/readiness controls, existing Studio editing, overlays, productivity tools and mobile overflow.
- Packaged service/desktop and installer/module-placement checks passed. The frontend test module is not installed in the product.

## Resulting behavior

Enable the FDGCast canvas in Vertical Studio, then choose FDGCast Vertical Studio in OBS Settings → Stream → Enhanced Broadcasting → Additional Canvas with Twitch as the main service. OBS sends both formats through that connection. No second ordinary Twitch output or key is needed. The native main encoder is never replaced.

YouTube Horizontal and YouTube Vertical have distinct presets and key guidance. Direct portrait outputs are enabled for YouTube, TikTok, Instagram and Vimeo. TikTok requires account-provided encoder credentials; Instagram requires eligible Live Producer access; Vimeo requires an eligible live-event plan. Chat connection and LIVE Studio access do not grant encoder publishing access.

Studio RTMP outputs can share the registered canvas render. Compatible H.264/AAC encoders are shared where possible when main encoders cannot be reused. Additional encodes still need CPU/GPU headroom. Unsupported legacy portrait outputs are blocked on save, assignment and start, while stopping/repairing them remains possible and saved keys are preserved.

## Operator checks still needed

- Real Twitch Enhanced Broadcasting negotiation, Inspector data and mobile playback on the user's GPU/account.
- Private YouTube dual-feed test with separate keys, plus actual TikTok/Instagram/Vimeo broadcasts if account access exists.
- Hardware encoder/slot limits, resource headroom, network outages/reconnects, profile/scene-collection variations and live scene transitions.

The earlier successful rc.1 installer does not include these latest changes. No stable release, Hub deployment or installation on the user's streaming computer was performed.

## Platform sources and verification scope

- Twitch: https://help.twitch.tv/s/article/dual-format-vertical-video — Enhanced Broadcasting and Additional Canvas.
- YouTube: https://support.google.com/youtube/answer/2474026 — second encoder key for a custom vertical feed in one broadcast.
- TikTok official regional OBS guide: https://seller-uk.tiktok.com/university/essay?default_language=en&knowledge_id=7738055662569218 — portrait 9:16 and account-provided RTMP URL/key. Does not prove universal access or a fixed follower threshold.
- TikTok portrait guidance: https://www.tiktok.com/live/studio/help/article/Enhance-visuals/Use-dual-layout-to-go-LIVE-in-portrait-and-landscape-simultaneously?lang=en
- Vimeo: https://help.vimeo.com/hc/en-us/articles/40727149468305-About-4K-Streaming — external encoder vertical formats; live-plan access remains necessary.
- Instagram's original Meta page was inaccessible. Official Streamlabs integration documentation describes 9:16 RTMP and Live Producer; current account eligibility needs dashboard confirmation: https://support.streamlabs.com/hc/en-us/articles/19796470357787-How-to-stream-to-Instagram
- Kick: https://help.kick.com/en/articles/7066931-how-to-stream-on-kick-com — standard output recommendations; no verified dual-format route established. Kick and other unverified routes are excluded conservatively, rather than claiming they universally reject all portrait signals.
- OBS 32.2.2 source: frontend/settings/OBSBasicSettings_Stream.cpp, frontend/OBSStudioAPI.cpp, libobs/obs-canvas.c. Persistent frontend canvases are eligible for Additional Canvas; EPHEMERAL canvases are excluded.
