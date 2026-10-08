# Hub integration delivered with FDGCast 0.7.0 Preview

The latest available website source, Hub 2.13.3 mobile-navigation ZIP, was
recovered and patched separately from this repository. Deploy that edited ZIP;
these changes are not live simply because the desktop installer was built.
Historical `/api/forgecast/v1/...` names remain compatible.

## Implemented in the website ZIP

- Twitch OAuth now requests the scopes used by follows, redeems, optional Bits,
  deletion, bans and timeouts, preserving chat read/write. Existing users must
  reconnect Twitch once to grant them. Channel eligibility/roles still apply.
- Google and other provider refreshes retain a refresh token when omitted by a
  response and persist rotated tokens. Concurrent refreshes in one server process
  share a request and reread the persisted account. This is not a distributed
  lock across independently running Hub processes.
- Refresh failures distinguish invalid/revoked grants, app configuration,
  account-admin policy and temporary outages. A still-valid access token can
  survive temporary refresh failure. Logs contain only platform/reason labels,
  not upstream bodies, chat, client secrets or tokens. An actually expired or
  revoked grant still needs creator reconnection. Google Testing mode can expire
  YouTube refresh grants after seven days; code cannot override that policy.
- OAuth callbacks reject a missing access token, failed profile lookup or missing
  channel identity before saving a misleading connection.
- Kick uses an explicit broadcaster ID, reuses the correct existing webhook
  subscription and validates each subscription result instead of treating HTTP
  200 alone as success. Signature/raw-body/timestamp verification remains intact.
- Private `/api/forgecast/v1/kick/diagnostics` returns subscription time, receipt
  time and retained count for the paired creator, without message contents.
  Hub Settings shows the last received chat time or no receipt in its retained
  window. Subscription readiness remains separate from message delivery.
- Events return stable IDs, statuses, timezone-aware dates, instructions and
  accepted participant names. The earlier slug-only response left the new dock
  empty. Only the creator's owned/going/accepted events are returned; pending
  invitations are excluded.
- FDGCast page and changelog now describe 0.7.0 accurately. Installer and matching
  same-host update manifests are bundled, with 0.6.0 retained for rollback.

## Deployment and live check

Deploy the complete edited Hub source, including `public/downloads/` and
`releases/`. Keep the existing platform secrets, encryption key, database and
BASE_URL unchanged. The normal server startup migration remains in use; this
patch does not need an additional migration. See the ZIP's
`docs/FDGCAST_0.7.0_INTEGRATION.md` for exact steps and remaining limitations.

Confirm the public installer download and `/fdgcast/releases/latest.json` return
200 without sign-in. Close OBS and Companion before installing. Reconnect Twitch,
reconnect YouTube if it has an expired grant, then Sync linked accounts. Send a
fresh Kick message and compare the Hub receipt with the OBS chat dock. Select an
upcoming Hub event and verify its title, time and accepted people in the optional
Today’s Events dock.

## Reference: platform requirements and live troubleshooting

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
