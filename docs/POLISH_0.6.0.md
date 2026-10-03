# 0.6.0 Preview refinement and verification

## Changes

- Stream Doctor Balanced default: sustained frame loss/reconnection waits eight
  seconds; Sensitive waits three, Relaxed fifteen. Recent rendering/encoding
  loss must be at least three frames and meet 0.5%/1%/2% thresholds. Major loss
  (5% or above) waits three seconds. Stable clearing uses five/ten/fifteen seconds.
  Output frame-loss ratios use available frame counters, with a three-frame minimum.
  Failed/stopped outputs can warn after three seconds. Telemetry loss is shown
  immediately as unknown but Windows warnings wait for persistence. Continuing
  issues notify once; significant escalation or a new episode can notify again.
  Normal bitrate changes and CPU readings do not generate alerts. GPU attribution
  is not measured; suggestions are possibilities rather than proven causes.
- Audio Guard retains its 30/60/120-second warning/notification/optional sound
  stages and custom WAVs. Removed the automatic five-minute repeated toast;
  the optional two-minute sound no longer generates a duplicate toast.
- Twitch Events now contains only follows, channel point redeems and incoming
  raids, using dedicated official EventSub subscriptions. Redelivery is deduplicated.
  Each optional subscription is independent; missing event permissions do not
  stop chat. Unknown EventSub topics cannot clear unrelated chat messages.
- MultiChat defaults to platform icon + viewer + message, with original channel
  in the hover tooltip. Appearance menu: text size, spacing, icon size, timestamps,
  name colors, optional creator avatars and optional original channel labels.
  Existing explicitly saved appearance preferences remain respected. The platform
  selector sits above the input so narrow docks give the draft usable width.
- Offline docks offer Open app. OBS already autostarts Companion; offline requests
  also offer to launch it. Safe audio settings/ack/snooze actions can resume within
  twenty seconds. Chat drafts stay available; live broadcast requests require a
  fresh click after recovery. Bridge credentials are reread on each poll.
- Companion Overview focuses on diagnostics, events and controls; duplicate chat
  removed. Connection language and tooltips simplified, OBS port tucked into
  advanced settings. Hub sync errors do not mark independent working chats offline.
- Twitch restarts with refreshed authorization so subscriptions use new scopes.
  Terminated YouTube adapters are recreated on account sync. YouTube malformed
  items cannot stall a page and sending without an active broadcast is explained.
  Kick malformed relay IDs/payloads are skipped independently so valid rows continue.
- Update checks, OBS Control notice and Companion banner; installed/latest versions,
  release notes, manual installer download and persistent Later. See UPDATES.md.

## Hub account work

Enable Twitch user:read:chat and user:write:chat for chat. New follows need
moderator:read:followers; redeems need channel:read:redemptions (or management
permission). Reconnect Twitch in the Hub after adding scopes. Events use the
streamer's own authorized channel. Incoming raid subscriptions have no additional
scope; the app still needs a valid broadcaster user token. Optional subscription
failures appear in the Events tooltip; sync accounts to retry.

Kick receiving still depends on the Hub subscribing to chat.message.sent with
its events:subscribe permission, verifying webhook signatures, and exposing the
existing /api/forgecast/v1/kick cursor relay to paired users. Replies need Kick
chat:write. FDGCast verifies the receiving broadcaster ID against the linked
account. Subscription-ready status does not prove webhook delivery.

YouTube uses authorized active-liveBroadcasts discovery and liveChatMessages.list,
respecting pollingIntervalMillis and backing off on quota/rate failures. A live
broadcast with chat enabled is required. API quota is finite, and polling is not
an unlimited/free chat transport. Missing/ended chats return to automatic discovery.
The Hub owns OAuth refresh; manual test tokens cannot refresh themselves. Pending
Google consent verification can prevent access for users; this installer cannot
bypass it. Sending needs an OAuth scope supported by liveChatMessages.insert
(e.g. youtube.force-ssl). Brand-account authorization must select the channel that
owns the broadcast. Multiple simultaneous broadcasts use the first returned active
chat; per-broadcast selection is not added in this pass.

## Verification boundaries

Automated fixtures cover platform normalization, sending targets, moderation,
Twitch event scopes/conditions/redelivery, malformed relay messages, doctor timing,
credentials isolation, update version/link/size/dismissal handling and native
payloads. Windows CI compiles the OBS module, checks Companion in Chromium,
packages the executable and smoke-installs it. These checks cannot prove real
account delivery or physical OBS dock dragging/resizing. Check on a real stream:
Twitch/YouTube/Kick independently and together; follow/redeem/incoming raid;
disconnect internet/Companion/OBS then reconnect; narrow/short and docked/floating
views; chirp/custom WAV and notifications with Windows Do Not Disturb off.

Website update publishing remains a separate deployment: this repository cannot
make the Hub's public installer/feed exist by itself.
