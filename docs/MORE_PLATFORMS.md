# Additional platform support — next FDGCast build

Implemented on `next/more-platforms`, based on verified chat-autoscroll commit
`36d7764`. The current 0.8.0 installer and Hub are unchanged.

## Streaming destinations

The same platform catalog drives Companion and the native OBS Add stream dialog.
Platform identity persists when saved/edited. All outputs continue to use the
existing shared OBS H.264/AAC encoder and canvas, Start All controls and protected
stream-key storage. At most eight secondary outputs are supported.

| Destination | Setup | Combined chat |
|---|---|---|
| Twitch | Default server + stream key | Existing adapter |
| YouTube | Default RTMPS server + stream key | Existing adapter |
| Kick | Linked-account server lookup or manual override + stream key | Existing Hub relay |
| Facebook Live | Standard RTMPS server + stream key; optional server override | Not connected |
| Rumble | Server URL + key from broadcast setup | New receive-only API reader |
| TikTok LIVE | Encoder server URL + key, if supplied by TikTok | New experimental receive-only reader |
| X Live | Server URL + key from broadcasting tools | Not connected |
| Instagram Live | Server URL + key from Live Producer if available | Not connected |
| LinkedIn Live | Eligible live event server URL + key | Not connected |
| DLive | Dashboard server URL + key | Not connected |
| Vimeo Live | Event server URL + key | Not connected |
| Other / Custom RTMP | Service-provided server URL + key | Not connected |

Facebook defaults to `rtmps://rtmp-api.facebook.com:443/rtmp/`, matching
[OBS's official service configuration](https://github.com/obsproject/obs-studio/blob/master/plugins/rtmp-services/data/services.json).
The custom server override remains available.

Selecting a platform does not grant LIVE eligibility, create its broadcast, or
publish a platform preview. Complete any platform-side Go live confirmation.
Independent encoders and vertical output are not included. Native “active” status
means the OBS output is active; it does not verify viewer playback.

Trovo is excluded because its official streaming shutdown was June 30, 2026:
[official announcement](https://support.trovo.live/category/8/article/2394).

## Rumble chat

In Connections, paste the private Live Stream API URL from
[account settings](https://rumble.com/account/livestream-api). This URL is a
credential and stays in the existing local vault (Windows DPAPI; session-only on
other operating systems). It is excluded from public state, diagnostics and
preference backups; feedback redacts the URL and its embedded API key.

An optional video ID filters one broadcast. Blank reads all active broadcasts
returned by that account's API. The reader runs independently of multistream,
checks every five seconds, backs off on failures, and restores saved connections
on startup. Redirects and non-Rumble hosts are refused; response size is bounded.

[Rumble documents](https://rumble.support/help/how-to-use-rumble-s-live-stream-api)
a recent-message window of up to 50 messages. Busy chats can have gaps. The API
example does not supply stable message IDs, so same-user, same-text, same-time
messages are deduplicated. Rants and other audience events are not added in this
pass. Replying and moderation remain on Rumble.

## TikTok LIVE chat and events — Experimental

Enter the creator's `@username`, explicitly enable the experimental reader, and
connect while a public TikTok LIVE is running. The LIVE can be started by phone,
LIVE Studio or another encoder; no FDGCast streaming destination is needed.
The reader requires no TikTok password or stream key.

The pinned `TikTokLive==7.0.1` dependency reads comments and LIVE activity and uses its default
third-party signing service. This is an unofficial integration, subject to
protocol changes, service availability and connection limits; no uptime guarantee
is made. [Library documentation](https://isaackogan.github.io/TikTokLive/).

Messages have TikTok identity, deduplication, OBS platform/channel filters and
existing chat-overlay support. Neither TikTok nor Rumble is offered as an
outgoing message target; reply/moderation controls are disabled for these readers.
Connections disconnect cleanly and recover with bounded retry delays.

Combined Events now receives follows, TikTok gifts, subscription notifications,
likes and shares. Select categories in **Combined Events → Event categories and
tests**. New configurations include follows and TikTok gifts by default;
existing saved category choices remain unchanged. Enable subscriptions, likes
and shares as desired. TikTok gifts are separate from gifted subscriptions.
Likes and shares become bounded summaries roughly every 10–20 seconds while
connected, and remaining summaries flush on disconnect. Gift streaks emit only
at completion, using the final cumulative count; interrupted unfinished streaks
are not invented. Subscription notifications do not imply verified purchases,
renewals or revenue. No money/coin conversion is displayed.

Stable room/message IDs and gift-streak IDs deduplicate observed activity with
bounded memory, plus the existing persisted event checkpoint. Summary packet
tracking is retained across automatic reconnects in the same reader, not across
process restarts. This is a live reader, not a follower-history API: offline
follows, missed events and complete replay/backfill are unavailable. LIVE activity
can work even when the FDGCast OBS output is stopped or no OBS is connected.
Paid live overlay access remains subject to existing entitlements; TikTok alert
categories follow the same selected event filters.

## Validation and remaining release work

- Python suite: 205 tests passed in the isolated runtime with pinned dependencies.
- Dependency resolution/check: passed; JavaScript syntax and patch whitespace checks passed.
- Actual TikTok protobuf event model exercised in tests; no real LIVE connection used.
- Rumble chunked JSON transport, duplicate replay, private URL validation, failure
  redaction, cancellation and credential removal covered.
- Facebook default and override, manual server requirements, platform identity and
  Start All payloads covered.
- Browser checks updated for all new choices and chat forms. Local Chromium binary
  download failed, so browser behavior is not yet verified.
- Native Windows compilation, frozen dependency packaging, installer smoke tests,
  and real platform video/chat delivery are still required before an installer release.

No Hub, Discord bot or Twitch extension changes were made.
