# FDGCast 0.9.0 Preview

Windows x64 / OBS Studio 32.2.2. Full release remains reserved for 1.0.0.

## Added

- Named Facebook Live, Rumble, TikTok LIVE, X, Instagram, LinkedIn, DLive and Vimeo
  destinations in Companion and OBS, alongside Twitch, YouTube, Kick and Custom RTMP.
  Facebook has a standard RTMPS default and an optional server override. Others
  require the server and key provided by the platform; account eligibility still applies.
- Receive-only Rumble chat through the creator's private Live Stream API URL.
- Experimental, receive-only TikTok LIVE chat by username, independent of multistream.
  A public LIVE must be running; the unofficial reader uses a third-party signing service.
- Overlay Studio: saved designs, chat, emote float/rain/burst effects, activity alerts,
  plain text, manual goals, per-widget appearance/position/platform choices, sample
  preview, duplication and design import/export.
- Independent revocable URLs per design, with multiple widgets combined in one
  Browser Source. Bounded effects, reduced motion, hidden-source pause and lighter
  static-design refreshes. Actual resource use still needs OBS testing.
- Verified paid/complimentary access gates for live overlay feeds, including the legacy
  chat overlay. Designer and labelled sample previews remain available without paid access.

## Changed and fixed

- Tools tab now contains overlays, the audio test, upload calculator and backup/restore.
  Help focuses on guidance and support.
- Native chat preserves automatic following through dock resizing, font changes and
  late image loading. Intentional scrollback stays paused; Jump or Ctrl+End resumes it.
- Destination editing retains platform identity.
- Read-only chat readers do not offer unsupported outgoing messages or moderation.

## Installation

Close OBS and FDGCast Companion, then install over the existing version. Pairing,
protected stream keys, saved preferences and existing dock identity are preserved.
Run OBS and Companion, sync linked accounts and check destination previews before
broadcasting. For overlays, use the saved design's URL and matching canvas dimensions.

## Website dependency

The existing authenticated account-sync response must include
`entitlements: {fdgcast_overlays: true|false}` computed for the pairing token owner.
The recommendation is Supporter access, preserving official FDG/admin/valid grants
and future eligible Business access through the shared entitlement service.
No new checkout or pricing is activated by this installer. Until the Hub update ships,
live overlays are locked while sample preview/designs remain available.
See [Overlay Studio handoff](OVERLAY_STUDIO.md). No Hub source or live site was changed here.

## Preview limitations

Facebook and the other new video-only destinations do not have combined chat.
Rumble's recent-message window can miss busy chat. TikTok is unofficial and can break
when TikTok or its signing service changes. TikTok/Instagram destinations share the
existing OBS canvas; independent vertical output is not included. Manual goals are
not automatically counted audience totals. Events depend on existing platform access
and delivery. Live platform video/chat, long-stream recovery, dock behavior, paid
access against the deployed Hub and real upgrade use still require creator testing.
