# FDGCast 0.8.0 Preview

This build combines the prepared Companion tools with YouTube streaming chat
and clearer Kick delivery diagnosis. Windows x64 target: OBS Studio 32.2.2.

## YouTube quota and recovery

Chat uses Google's official StreamList gRPC connection instead of repeated
liveChatMessages.list polling. A quiet chat keeps its connection open. Reconnects
resume from the last nextPageToken; switching broadcasts resets that cursor.
Hub OAuth refresh reopens the connection with the new token. Existing message
identity, badges, events, replies and moderation remain in the combined dock.
Tombstones remove previously displayed messages; chat-ended events trigger discovery.

Explicit daily quota errors suspend chat and broadcast enumeration until the
next midnight-Pacific reset (with a one-minute margin). Other API exhaustion
backs off for one hour. Network failures back off, and permission/authorization
messages remain distinct. No automatic polling fallback spends quota while the
streaming connection fails. Chat writing still uses the official REST endpoint.

This reduces quota use; it does not replenish quota already exhausted or provide
unlimited quota. Quota is shared by the Google developer project. Existing 0.7
clients still poll until upgraded. Project quota increases/audit remain a separate
Google Cloud task as the user base grows. Google verification is independent.

Protocol source: https://developers.google.com/youtube/v3/live/streaming-live-chat
and https://developers.google.com/youtube/v3/live/docs/liveChatMessages/streamList.
Generated protocol definitions use Google's Apache-2.0 sample. Added its required
Duration import. Build/runtime dependencies are pinned; no client-secret changes.

## Kick connection diagnosis

Existing subscriptions count as ready only when the event, broadcaster, webhook
method and subscription ID match. Changing channels invalidates old subscription
and delivery status. The Companion optionally reads the Hub's private receipt
diagnostics once a minute; older Hubs can continue relaying without that endpoint.

Statuses distinguish unverified delivery, no recent accepted Hub messages,
Hub receipt without matching Companion messages, and actual Companion receipt.
Malformed or wrong-channel relay rows retain an actionable warning. These changes
do not fix server signature rejection: the Hub builder is addressing its 401s.

## Companion Help tools

- Guided 20-second audio recording test, early finish, playback and listening
  checklist. Requires OBS connected and neither streaming nor already recording.
  Only stops its own recording on the same connection. Uses your OBS recording
  settings; cannot certify platform audio or VOD playback.
- Problem/feature feedback with preview, optional diagnostics, download, and
  explicit sending of the reviewed payload to the existing private Hub reports
  endpoint. Edit invalidates preview. Review free text/output names for privacy.
- Preference backup and reviewed restore with OBS closed. Preserves existing
  credentials; new destination names become unchecked placeholders. Excludes
  stream keys, tokens, server URLs, source assignments, custom WAVs and dock layout.

## Installation and validation

Close OBS and Companion before upgrading. Pairing, saved credentials, existing
outputs and dock settings remain in their current locations. FDG icons continue
on the installer, executable, desktop window and taskbar.

Source tests cover streaming serialization/metadata using a local gRPC server,
idle connection lifetime, cancellation, token/broadcast changes, cursor recovery,
quota resets across DST, error privacy, tombstones, ended chats and relay diagnostics.
Windows CI also runs existing and new UI checks, native compilation, frozen
streaming-dependency smoke checks, desktop icon and installer placement checks.

Real-account YouTube StreamList delivery, Kick delivery after the Hub fix,
Windows OBS docking and multistream lifecycle still require live testing before
calling this a full public release. Simulated/local tests cannot prove those.
