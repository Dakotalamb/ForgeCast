# FDGCast 0.7.0 Preview

Built for Windows x64 / OBS Studio 32.2.2. Preview: local automated validation
is distinct from real-account delivery and testing docks in a running OBS UI.

## Changes

- OBS Chat: platform and original-channel filters, Pause / Jump to latest,
  optional channel avatars, badge labels, reply context, highlighted-message
  styling, alternating backgrounds and per-dock reset. Composer visibility now
  includes its destination selector.
- Right-click a viewer name for copy, account-specific recent messages, profile,
  mention/reply, highlight and supported moderation. Twitch delete/timeout/ban
  require the corresponding token scopes. Shared messages from another original
  channel cannot accidentally be moderated in your own channel. YouTube actions
  are attempted using its authorized account and subject to server permissions.
  Kick moderation remains in native Kick chat until its API integration is built.
- Send individually or to all currently connected platforms, with a confirmation
  listing platforms and per-platform delivery results. Partial failure retains
  the draft; retry the failed platform individually to avoid duplicating success.
- YouTube: refresh active broadcasts and choose manually or automatically.
  Corrected Google branding-vs-writing-permission wording. Expired tokens still
  require the Hub to refresh them or the creator to reconnect.
- Kick: avoids repeatedly resubscribing when the token/channel are unchanged.
  Explains subscription readiness separately from verified message receipt.
  Hashed dedup IDs and Kick relay cursor are checkpointed without chat content.
- Optional subscriptions/gifts/Bits/YouTube paid events and memberships. Default
  remains follows/redeems/raids. Bits require bits:read; Twitch chat notifications
  supply supported subscription/gift events. No third-party tips integration.
  Category toggles, merge into OBS chat, acknowledgement and labelled tests.
  Bounded event history survives restart; simulated events are not persisted.
- Save destination-selection presets in Companion or OBS Multistream menu.
  Presets select the next Start All and never start or stop a broadcast themselves.
- Optional Today’s Events OBS dock: selected event, local time, instructions and
  accepted participants from the Hub. Hidden on its first introduction; enable
  through OBS Docks. RSVPs never imply live status or start outputs.
- Preflight in OBS Control, plus Companion fixes/navigation, selected event and
  optional recording expectation and fresh recording-space information reported by OBS. Missing telemetry stays unknown.
- Searchable Help with first-stream walkthrough, troubleshooting, official OBS
  resources, upload-budget calculator, compatibility and update recovery guidance.
- Stream Doctor optional chirp/custom WAV, independent of Windows notifications.
  Audio Guard optional sustained input near-clipping warning and routing checks
  against a creator-selected VOD track. No claim of viewer playback or automatic
  detection of the platform’s VOD encoder settings.
- Optional transparent chat overlay: immediate or queued highlights, or recent combined
  public chat. Basic themes, font/spacing controls and separate revocable read-only link; disabled by default. Deleted
  messages are excluded. No account tokens or OBS controls in its feed.
- Session summaries/export: locally observed duration, destinations, performance
  failures, audio warnings and received per-platform message/event counts.
  Counts are accumulated beyond the displayed chat window; outages are unobserved.
- Diagnostic preview before export/sharing, known limitations and support links.
  Consistent 0.7.0 branding and existing FDG icons preserved in packaging.

## Validation

166 Python tests passed locally after the final local checkpoint/overlay queue fixes.
Windows native compilation, expanded Chromium UI checks, desktop app/installer
smoke checks and installer hashes must be recorded after CI completes.

## Required live verification

- Google refresh-token persistence/refresh and actual read/write delivery.
- Kick signed webhook receipt, authorized Hub relay filtering and fresh messages.
- Twitch newly granted follows/redemption/moderation scopes and actual events.
- OBS right-click actions, dock resizing/arrangement, pause/reconnect, custom WAV,
  near-clipping duration, selected VOD routing and independent output failures.
- Overlay Browser Source during real moderation and Companion interruption.
- Hub event field shape against the deployed website contract.

## Outside this repository

Hub/Discord/Twitch extension updates require their latest source. Cloud restream,
paid billing, a public hosted chat page, sponsor analytics, independent encoders,
vertical canvases, delegated collaborator chat, platform title/category mutation,
dedicated Stream Deck/Streamer.bot plugins and hardware-derived auto settings
are not implemented here. See HUB_HANDOFF_0.7.0.md and IMPLEMENTATION_STATUS.md.
