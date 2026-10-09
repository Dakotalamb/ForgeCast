# Hub handoff for FDGCast 0.8.0 Preview

No Hub source or live deployment was changed in this FDGCast task.

## Kick delivery fix remains separate

Live Heroku log evidence: POST /api/forgecast/v1/webhooks/kick at
2026-10-09T02:25:25.654531Z returned 401. Companion relay GET requests returned
200 with no messages. That identifies verification rejection, not its exact
cause. The website builder is checking current public-key fetch/cache/rotation,
raw-body/header preservation, timestamp checks, and safe rejection diagnostics.
Keep signature verification enabled. Verify real Kick chat after deployment.

Companion 0.8.0 optionally calls the existing paired-user private endpoint
GET /api/forgecast/v1/kick/diagnostics once per minute. It understands
{delivery_verified: boolean}; older Hubs without it remain compatible.
The diagnostic must be scoped to the paired creator and contain no chat/tokens.
Hub receipt is not proof of Companion receipt. Existing relay message schema
and account/token endpoints remain unchanged.

## YouTube

Companion now reads using Google's official StreamList gRPC connection and
keeps OAuth token refresh on the existing Hub connections endpoint. It needs
outbound access to youtube.googleapis.com:443. It uses the same linked user
token, with existing YouTube send/moderation REST actions. No developer-app
callback URL, secret, Hub migration or OAuth redirect change is needed for
this transport update.

Daily API quota is shared by the Google project. New streaming clients reduce
polling; older installed clients will continue polling until upgraded. Google
quota/audit/verification remains a website/developer-account task. An already
exhausted quota is not replenished by this installer or account reconnect.

## Preview release hosting after approval for distribution

Tested installer: FDGCast-0.8.0-preview-win-x64-setup.exe
Bytes: 17,242,239
SHA-256: 72947022d800fbff8fe7e4c13426507b2d8e3a83c0a92f5b07a334c6aef4e392
Target: Windows x64 / OBS Studio 32.2.2.
Build: https://github.com/Dakotalamb/ForgeCast/actions/runs/37876362565

When choosing to distribute this preview, host that exact EXE at
/downloads/FDGCast-0.8.0-preview-win-x64-setup.exe and update the public
/fdgcast/releases/latest.json using docs/latest-release.example.json.
Preserve schema_version=1, platform=windows-x64 and version=0.8.0-preview.
Only update the feed after the download exists. The Companion shows a notice
but does not install updates automatically or restart OBS.

Use docs/RELEASE_0.8.0.md for the page/changelog. New Companion Help features
are guided recording/listen test, reviewed private problem/feature feedback
using the existing /api/forgecast/v1/reports endpoint, and credential-free
preference export/review/restore. Do not promise staff notifications or triage
that the backend does not implement.

## Full-release gate

Windows CI and 194 source tests passed; simulated UI/local gRPC tests are not
live service tests. Before calling this a full release, verify real-account
YouTube streamed chat/reconnect/new broadcast, Kick chat after the server fix,
OBS dock arrangement/restart and multistream lifecycle/audio routing. No 0.9.0
or stable 1.0 package is being claimed or published here.
