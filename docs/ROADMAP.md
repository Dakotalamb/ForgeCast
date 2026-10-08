# October 8 implementation checkpoint

See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for delivered features and remaining work, and [HUB_HANDOFF_0.7.0.md](HUB_HANDOFF_0.7.0.md) for the website dependencies.

# Production roadmap / remaining scope

## Gate 1: first usable private beta

- Build/load native module against the user's installed Windows OBS version.
- Finish live output lifecycle/error-signal tests and ABI packaging.
- Live-test the Hub OAuth callback and refresh flows on all three platforms.
- Validate real Twitch Shared Chat origin fields and cross-channel moderation.
- Move YouTube from polling to streamList with quota/error-aware recovery.
- Test Kick webhook signature, subscription and delivery on the deployed Hub.
- Finish browser accessibility/visual QA and Windows DPAPI tests.
- Redact platform errors/logs and introduce bounded structured diagnostics.

## Gate 2: Hub-connected suite

- Harden Hub pairing with narrowly scoped short-lived device grants and consent.
- Confirm creator consent before any cloud upload or moderator delegation.
- Event preparation with title/category validation on each supported platform.
- Live/ended heartbeat and existing Discord status-board integration.
- Retrieve platform-defined analytics without implying unique cross-platform users.

## Gate 3: broadcast parity

- Independent encoders/bitrates/audio routing and robust Start All orchestration.
- Vertical and additional canvases with linked scenes and output-specific overlays.
- Multicanvas replay/clip capture, one-click clip review and file management.
- Emotes/avatars/badges, activity filters, destination-explicit replies and moderation.
- Platform-rule-aware overlays separate from the private operator chat dock.

## Gate 4: differentiation

- Source/GPU/encoder profiling with measurements and calibrated confidence.
- Driver-event correlation (opt-in), safe incident snapshots and change timeline.
- Reversible emergency actions selected by the creator; no silent process kills.
- Preflight audio/capture verification and private-window warning research.
- Modular trigger/condition/action automation; explicit permissions and audit log.
- Phone/Stream Deck integrations, team-event presets and scoped remote monitoring.

Keep local chat and basic diagnosis usable without Hub sign-in. Paid cloud features
are a product decision, not implemented in this package. Do not promise free
unlimited hosted relays or storage before measuring operating costs.

