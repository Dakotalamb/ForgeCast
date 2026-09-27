# ForgeCast ↔ Forge Creator Hub API v1

The companion Hub source in `../../hub-work` implements this API. Deploy that
Hub update and run its migration before pairing. It is not live until deployed.

Hub Settings issues a creator-specific, revocable `fc_` token, displayed once
and stored only as a SHA-256 hash. Use HTTPS and `Authorization: Bearer fc_...`.
Treat it as highly sensitive: it can retrieve the owner's platform access tokens.
OAuth client secrets and refresh tokens never go to the desktop companion.

| Endpoint | Purpose |
|---|---|
| `GET /api/forgecast/v1/connections` | Platform identities, refreshed access tokens or reconnect error |
| `GET /api/forgecast/v1/events` | Up to 50 current/upcoming owned or accepted events |
| `GET /api/forgecast/v1/kick?after=N` | Up to 100 Kick chat messages after cursor N |
| `POST /api/forgecast/v1/reports` | Confirmed diagnostic upload; last 25 retained |
| `POST /api/forgecast/v1/webhooks/kick` | Public signed Kick webhook; no bearer token |

Kick signs the raw body with its published RSA key. The Hub verifies the
signature and timestamp and deduplicates deliveries. Configure this public
HTTPS endpoint in the Kick developer app, then reconnect Kick in Hub Settings
to subscribe to `chat.message.sent`. Hub relay rows are pruned after 24 hours
on webhook receipt; this is not a permanent chat archive. The dock polls Kick
approximately every five seconds. Uploading a report requires confirmation.
