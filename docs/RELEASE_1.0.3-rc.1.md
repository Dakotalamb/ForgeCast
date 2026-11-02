# FDGCast 1.0.3-rc.1 — TikTok LIVE chat and events preview

Connect a public LIVE creator's TikTok username in Companion → Connections.
Read chat and follows, gifts, subscription notifications, likes and shares
without adding a TikTok streaming destination. The creator can broadcast using
phone, LIVE Studio or another encoder. FDGCast does not need OBS streaming,
a TikTok stream key, or a second video encoder to read LIVE activity.

Choose event types in Combined Events → Event categories and tests. Follows and
TikTok gifts are on by default for new configurations; existing category choices
are preserved. Subscriptions, likes and shares are optional. Likes and shares
are grouped, gift streaks count once when completed, and stable activity IDs
protect against replays within bounded deduplication/checkpoint limits.
TikTok gifts are distinct from gifted subscriptions. The OBS Events dock shows
the platform and readable labels. Paid overlay permissions are preserved.

This is an experimental, unofficial, receive-only LIVE reader using the existing
third-party signing service. It does not provide offline follow history, guaranteed
catch-up, sending, moderation, OAuth account management or TikTok broadcasting
access. Availability depends on a public LIVE and the service's current access.

Validation includes the pinned TikTokLive 7.0.1 real protobuf event classes,
feed filtering, persisted history, duplicate IDs, gift streaks, grouped activity
and client cancellation. Actual TikTok delivery needs a real LIVE smoke test.
Close OBS and Companion before installing this preview. Stable remains v1.0.2.
