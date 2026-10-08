# Website handoff for FDGCast 0.7.0 Preview

FDGCast is the desktop/OBS repository. Do not claim these backend changes were
made here. Apply to the current deployed Hub source and test real accounts.
Historical `/api/forgecast/v1/...` route names stay unchanged for compatibility.

## Fix the failures seen in Connections

1. YouTube: Connections must refresh expired access tokens server-side before
   returning them. Persist the refresh token encrypted. If a refresh response
   omits a new refresh token, preserve the existing one. Handle invalid_grant
   as a reconnect-required state without breaking Twitch/Kick. Authorize the
   correct Google/Brand channel. Writing/moderation need `youtube.force-ssl` or
   `youtube`; branding verification is separate. Never return refresh tokens or
   OAuth client secrets to Companion. Check Google test-mode expiration and
   revoked grants; do not mislabel every 403 as expired authorization.
2. Twitch: OAuth currently lacks `moderator:read:followers` and
   `channel:read:redemptions`. Add those to consent and reconnect the user.
   Redeems still require an eligible channel with channel points. Optional:
   `bits:read`, `moderator:manage:chat_messages`,
   `moderator:manage:banned_users`. Preserve chat read/write scopes. Explain
   permission upgrades and allow users to decline optional capabilities.
3. Kick: subscription exists but delivery is unproven. Verify the app’s exact
   HTTPS webhook `/api/forgecast/v1/webhooks/kick`, raw-body RSA signature and
   timestamp checks, stable message-ID dedup, enabled `chat.message.sent`
   subscriptions with `events:subscribe`, and account/broadcaster matching.
   The callback is the OAuth redirect; it is not the webhook. Trace a fresh
   message from receipt through its authorized relay row and Companion poll.
   Keep log contents redacted; never log signatures/tokens/raw chat by default.

## Existing API compatibility

`GET /api/forgecast/v1/connections`: `{connections:[{platform, user_id,
username, client_id, access_token}]}` with redacted per-account reconnect errors.
Return refreshed short-lived access tokens only to the paired creator, with
no-store headers and proper revocation. This existing powerful integration grant
must be protected; changing to narrower device grants needs a migration.

`GET /api/forgecast/v1/kick?after=N`: `{messages:[{id:integer,payload:{
message_id,broadcaster:{user_id,channel_slug},sender:{user_id,username},content}}]}`.
Filter by the paired creator on the server; enforce cursors and limits. Companion
also validates the broadcaster, but that does not replace server authorization.

`GET /api/forgecast/v1/events`: `{events:[{id,title,starts_at,game_name,
status,instructions,url,participants:[{display_name,status}]}]}`. `starts_at`
must be ISO 8601 with timezone (UTC Z preferred). Return only owned or accepted
commitments the paired creator can access, including authorized private events.
`url` should be a relative Hub path or same-host HTTPS link. Accepted/confirmed/
going participant statuses are displayed as RSVPs, never live telemetry.
Existing minimal id/title/starts_at responses remain usable; extra fields can
be added progressively. Handle cancellation and schedule changes accurately.

## Release feed and support

Publish `/fdgcast/releases/latest.json` using latest-release.example.json, after
hosting the tested installer at its matching download URL. Use 0.7.0-preview
only once the artifact is ready. Do not advertise a nonexistent newer version.
The public JSON feed does not take creator credentials; existing update trust
rules permit saved Hub origin or this repository’s GitHub release download path.

Support/report routes already exist. Add private creator-reviewed report intake,
reproduction fields and feature requests if not already available. Public GitHub
issues must never receive pairing codes or private event content. Separate FDG
failures from platform denials. Offer known issues and actual supported versions.

## Ecosystem work requiring its own implementation

Audit current website scheduling/discovery/privacy/local-time/ICS/repeats first.
Then add availability/conflict warnings only for demonstrated coordination needs.
Discord needs grouped idempotent schedule updates, privacy, quiet periods and
edit/cancel handling in its own queue worker. Twitch extension setup/error copy
and schedule payloads need validation against the released extension and review
requirements; do not silently alter approved extension files from this repo.

Future live heartbeats, title/category assistance, cloud relay, analytics, paid
billing, delegated chat and integrations need explicit schemas, consent,
permissions, costs and end-to-end tests. They are not implied by an RSVP.
