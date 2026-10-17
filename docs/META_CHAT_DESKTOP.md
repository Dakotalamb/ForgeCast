# Facebook / Instagram LIVE comments and Rumble chat

This desktop change implements schema version 1 from the October 17 Hub handoff.
It does not deploy the Hub or grant Meta permissions. Core chat stays free;
existing official-Hub overlay entitlements are unchanged.

## Creator setup

1. Deploy and configure the accompanying Hub update according to its
   `docs/META-CHAT-SETUP.md`, including its real login callbacks and Instagram
   webhook. Complete the current Meta permission/review requirements.
2. Pair Companion with that Hub. In Connections choose Connect Facebook or
   Connect Instagram, using the same Hub login that owns the pairing.
3. Facebook reads the selected managed Page's live-video comments; Instagram
   reads professional-account LIVE comments. Sync linked accounts after login.
4. Check the per-platform status. Waiting for a broadcast or a verified
   subscription alone does not prove actual comment delivery.
5. These are receive-only readers. Use each platform for sending/moderation.

## Desktop contract

Discovery uses `chat_connections` from authenticated
`GET /api/forgecast/v1/connections`. Reader requests use
`GET /api/forgecast/v1/chat?platform=facebook|instagram&after=<decimal cursor>`
with the existing pairing bearer in the Authorization header. Meta credentials
are never requested from the operator or sent to Companion.

Each platform keeps its account/generation cursor in memory, preserves it during
transient failures and drains full pages before the normal five-second poll.
A restart may fetch retained messages, with existing local deduplication applied.
IDs include platform, account, generation and comment ID. Pages are validated
before ingestion; timestamps must have a timezone and content is plain text.
Responses are bounded to 2 MB, 100 messages and a 15-second timeout. Redirects
are rejected. Failed requests back off with jitter, capped at 120 seconds.

Account/generation/pairing changes remove that platform's old visible messages
and highlight references. Disabled, disconnected, setup-required and authorization
failure states clear stale messages. A 401 clears both Meta feeds and suspends
relay ingestion until pairing is repaired and explicitly synced. Other platform
readers remain independent. Old in-flight responses cannot restore prior-owner
messages. The Hub remains authoritative for account ownership and permissions.

## Rumble

Overview has a Connect Rumble chat shortcut. Connections places the Rumble chat
card prominently, with a masked private API URL, optional video ID, status and
Connect/Disconnect controls. The OBS Chat dock has a setup action leading to
Companion. The private URL stays in the existing local vault; the Hub has no
Rumble reader or credential field. A separate Rumble video output is not required.

Existing limits remain: receive-only, recent-message window, bounded polling and
backoff. Real busy broadcasts can have gaps. Do not promise complete history.

## Release checks

Run the Python suite with requirements.txt, browser QA, renderer checks and the
Windows native/installer workflow. A successful build does not verify a real
Facebook, Instagram or Rumble broadcast. Creator testing must cover authorized
comments in OBS, platform filters/icons, account switches, reconnects, revocation,
private-URL masking and free/paid overlay behavior before stable release.
