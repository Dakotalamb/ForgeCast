# FDGCast 1.0.3 — TikTok LIVE activity and a clearer activity feed

- Read TikTok LIVE chat, follows, gifts, subscription notifications, likes and shares using the existing creator-username connection. FDGCast does not need to stream to TikTok, connect to OBS, or create another video encoder to receive this activity. The creator must still have a public TikTok LIVE running through a phone, LIVE Studio or another encoder.
- **Combined Activity Feed** replaces the Combined Events name in Companion and the OBS dock. Each activity card shows a local platform icon alongside platform/channel text. Saved OBS dock identity and placement are preserved.
- Gift streaks count once when completed, using their final count. Likes and share notifications are grouped rather than flooding the feed. Stable room/message and gift-group IDs provide bounded replay protection.
- Select categories under **Combined Activity Feed → Choose activity types & test alerts**. Follows and TikTok gifts are enabled for new configurations. Existing saved choices are preserved; enable subscriptions, likes and shares as desired.
- TikTok gifts are distinct from gifted subscriptions. Selected TikTok activity can appear in existing overlay alerts, subject to the existing paid overlay entitlement.

- A clearer Overview gives the activity feed more room, with broadcast controls, Audio Guard and health checks alongside it. Recording/replay controls sit in a separate expandable section.
- Connections starts with OBS and Hub pairing, followed by linked platforms and direct LIVE readers. Updates and manual credentials sit below the main setup. Activity cards retain focus on unchanged refreshes and preserve scroll position when older activity is being read. Larger text, stronger contrast, platform names and clearer button emphasis improve readability. The version badge now uses the installed package version.

## Installation and setup

Close OBS and FDGCast Companion before installing. In Companion → Connections, enter the public LIVE creator's TikTok username and enable the experimental reader. No TikTok password or stream key is required for the reader. Broadcasting to TikTok remains a separate feature with its own account requirements.

## Validation and limits

The preview passed 255 regression tests, four Chromium UI suites, real OBS horizontal/vertical encoding and canvas persistence checks, packaged dependency/desktop checks, and Windows installer validation. Tests exercise the pinned TikTokLive 7.0.1 real protobuf event types, gift streaks, duplicate messages, grouped activity, history, filters and clean disconnect. The stable package repeats the automated release gates before publication.

TikTok reading remains an unofficial, experimental, receive-only integration using a third-party signing service. Actual TikTok LIVE delivery has not been verified in this build by the maintainer. No offline follower history, guaranteed replay/backfill, sending or moderation is provided. Incomplete gift streaks are not invented; grouped raw-packet deduplication persists across automatic reconnects in the same reader, not process restarts. Subscription notices do not establish billing status or revenue. TikTok changes and service limits may interrupt access.

Existing Facebook/Instagram chat still requires the separately configured Hub and platform access. No Hub deployment is included. See [platform setup](MORE_PLATFORMS.md) for details.
