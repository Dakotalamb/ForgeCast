# FDGCast 0.8.0 Preview

New chat filters/actions, searchable Help, optional Hub dock, overlays and session summaries.
See [release notes](docs/RELEASE_0.8.0.md), [roadmap coverage](docs/IMPLEMENTATION_STATUS.md) and [website handoff](docs/HUB_HANDOFF_0.7.0.md).

# FDGCast 0.6.0 preview

Refinement release: quieter diagnostics, focused Twitch Events, simpler OBS chat,
Companion recovery and update notices. See [refinement notes](docs/POLISH_0.6.0.md)
and [website update feed setup](docs/UPDATES.md).

OBS companion, Forge Creator Hub integration, and native multistream source for Forged Destiny Gaming.

**This is a developer preview, not a finished Aitum replacement.** A previous
version compiled a Windows installer and an OBS 32.2.2 native module. Installation in
OBS and live streaming still need validation. The local companion runs with Python;
all implemented platform adapters also need testing with your authorized accounts.
The Hub backend is maintained in its separate repository.

The Windows Actions workflow compiles the OBS module and companion and bundles
them with `packaging/FDGCast.iss`. Download the preview installer from the
successful workflow run's artifact. Close OBS before running the EXE, install,
then start the FDGCast desktop app from the Start menu. In OBS, open Docks →
FDGCast Chat, FDGCast Stream Doctor, FDGCast Multistream, or FDGCast Control.
The desktop app runs the local account and telemetry companion; daily chat,
diagnostics, and multistream controls are available in OBS. Test privately before
using it on a public stream. See
`docs/NATIVE_BUILD.md` before distributing any binary.

The first launch of 0.6.0 places Stream Doctor beside Sources, FDGCast Events
in the Event List area with Chat beside it, and Multistream beside Outputs. FDGCast Control shares the
Multistream space as a tab. In OBS, use the Control dock's **Arrange FDGCast
docks** button to restore that layout. To drag docks elsewhere, turn off
**Docks → Lock Docks**. OBS saves subsequent manual arrangements. Other plugins'
Outputs and Event List docks stay available; close them yourself if preferred.
Platform sign-in happens in the Hub. FDGCast's Connections tab pairs to the
Hub and syncs your accounts; raw API IDs/tokens live under Advanced for testing.
Chat in OBS includes Twitch, YouTube and Kick message targets; choose which
connected channel receives your message. Kick requires a linked Hub account
and a fresh account sync; the Hub must grant `chat:write`. FDGCast
Events collects available platform activity, OBS status, and Stream Doctor
incidents. Twitch follows and Kick alerts require additional platform scopes
and integrations; they are not included in this preview.

YouTube chat reading works with the Hub's current read-only permission. Sending
YouTube chat needs a broader Google scope and will require creators to reconnect
after Google approves it. This desktop build already includes the reply action
and a specific error when the current authorization rejects it. Keep the public
Hub on its verified scope until the broader scope is approved.

The display name is FDGCast. For upgrades, the OBS module and dock IDs still use
`forgecast` and the desktop companion still reads `%LOCALAPPDATA%\ForgeCast`
so existing dock positions, destinations and DPAPI-protected credentials survive.
The installer reuses the previous Inno Setup AppId and removes legacy shortcuts.

## Start with the safe demo

1. Extract this entire ZIP into a normal folder.
2. Install Python 3.11 or newer from https://www.python.org/downloads/windows/
   including the Python launcher (`py`).
3. Double-click `Preview-Demo.cmd`. The launcher creates a local virtual environment
   and downloads the dependency in `requirements.txt` from PyPI.
4. Your browser opens the dashboard. All demo messages/measurements are labeled
   DEMO. Live actions are disabled. Close the terminal to stop.

This does not install or alter OBS, change Windows settings, or connect an account.
Run only one companion instance at a time. The fixed local port is 17654.

## Connect real OBS measurements

1. Start OBS and enable Tools → WebSocket Server Settings → Enable WebSocket server.
   Keep authentication enabled; note the local port and password.
2. Run `Start-FDGCast.cmd` (without `--demo`).
3. Open Connections → Connect OBS and enter the port/password locally.
4. Run Preflight and inspect Stream Doctor. Stream/record/replay actions require
   confirmation. Do not test with a public live stream until verified privately.
5. Optional: add the URL printed in the console to OBS → Docks → Custom Browser
   Docks. Name it FDGCast. Re-copy the printed URL after restarting the companion.
   **This is a private operator dock, NOT a browser source/overlay.**

No native module is needed for main-output diagnostics, main OBS controls, or chat.

## What's implemented and what's not

| Area | This package | Verification |
|---|---|---|
| Desktop app | Dedicated FDGCast window for initial Hub, account and OBS connection setup | Windows app still needs live testing |
| Shared chat provenance | Platform + original broadcaster + chatter; dedup by source message ID | Unit tested with fixtures |
| Twitch adapter | EventSub messages/chat notifications/deletes/clears; send to configured receiving channel | Code implemented; live OAuth test needed |
| YouTube adapter | API polling with server interval; chat/activity/deletion; send | Code implemented; live token/quota test needed |
| Stream Doctor | Delta-based rendering/encoding/network classification; sustained thresholds/history; JSON report | Unit tested; real OBS validation needed |
| OBS controls | Authenticated v5 WebSocket, start/stop main stream/recording, replay | Mock-server integration tested |
| Preflight | Mute flags, reported disk space, OBS CPU/memory | Code implemented; not an audio/capture quality test |
| Multistream | Native OBS dock with destination setup, start/stop and status; shared H.264/AAC RTMP output engine, eight destinations, reconnect | Windows build passed; not live-tested inside OBS |
| Hub | Pairing token, OAuth account sync/refresh, events, reports, Kick relay | Source implemented; deploy and live-test Hub |
| Credentials | Windows DPAPI storage; session-only storage on other OSes | Memory path tested; Windows DPAPI needs Windows test |
| Kick chat | Verified webhook to Hub and five-second local relay | Source implemented; public HTTPS webhook/live test required |
| OAuth login/refresh | Hub OAuth for three platforms and periodic access-token renewal | Source implemented; live test needed |
| Vertical canvases / independent encoders | Not implemented | Roadmap |
| Start All / Stop All | Main stream and checked destinations | Build/fixture tested; live testing required |
| Twitch Events | Follows, channel point redeems and incoming raids | Scopes/conditions and redelivery tested; live permissions required |
| Updates | Startup/daily notices; changelog, manual download, Later | Needs public Hub release feed; see docs/UPDATES.md |
| Automation / team controls / source profiling / remote access | Not implemented | Roadmap |
| Emote images / creator avatars | Bounded image cache; optional creator avatars | Fixtures/build verified |
| Moderation actions / cross-channel replies | Not implemented | Roadmap |
| Sponsor analytics / audience counts / Discord writes / automatic event preparation | Not implemented | Roadmap |

### The important shared-chat distinction

By default each row shows a platform icon, ViewerName and message. Hover the icon
to see Box_Beard's channel, or enable original channel labels in the dock menu.
Twitch's `source_broadcaster_user_id`, `source_broadcaster_user_name` and
`source_message_id` take precedence over receiving-channel fields. The receiving
channel is retained separately. Missing source fields fall back to the receiving
channel; the app cannot invent origin data absent from a platform event.

Sending targets your explicitly configured receiving channel, not an inferred
origin channel. True cross-broadcaster replies and moderation require additional
authorization and are deliberately not simulated.

## Chat credentials (developer setup)

**Never send account passwords, access tokens, or stream keys to this chat.**
Deploy the included Hub update, connect Twitch/YouTube/Kick in Hub Settings, generate
a FDGCast pairing token there, and enter it with the HTTPS Hub URL in the local dock.
Click Sync Hub accounts. The Hub refreshes access tokens; the dock re-fetches them
periodically. You can also enter tokens manually in the local dashboard for testing.

Twitch: register your own app at https://dev.twitch.tv/console/apps and obtain a
user access token through Twitch's documented OAuth flow. Configure its Client ID,
authorized user ID and the receiving broadcaster/channel ID. Use `user:read:chat`
for reading and `user:write:chat` for sending. Reading other channels can have
additional permission requirements. Start by using your own channel. Twitch
Shared Chat source fields identify originating broadcasters when provided.

YouTube: enable the YouTube Data API in your Google project and use the authorized
broadcaster's OAuth access token and the active broadcast's `snippet.liveChatId`.
For sending, authorize an appropriate scope; the Hub requests `youtube`.
This is an API chat ID, not the public
video ID. The alpha uses `liveChatMessages.list`, respects `pollingIntervalMillis`,
and can consume significant API quota. Active broadcasts are discovered automatically on Hub account sync; typed quota
errors back off without restarting OBS. A future version can migrate to streamList. Your manually entered channel display name labels origin.

Saved Hub accounts sync automatically after restarting and every sixty seconds;
new YouTube live chats are discovered when the old broadcast ends. Manual chats must be reconnected.
For Kick, configure its developer app's public HTTPS webhook as
`https://YOUR-HUB/api/forgecast/v1/webhooks/kick`, then reconnect Kick in Hub Settings
to subscribe to `chat.message.sent`. Kick replies use the authorized user's
official chat endpoint and send only to that user's linked channel.

The app and installer use Forged Destiny Gaming's orange F icon. The installer
is still unsigned: adding an icon does not remove Windows SmartScreen's
"Unknown publisher" warning. Public distribution needs a trusted code signing
certificate, and even signed new builds may need time to gain reputation.

## Native multistream module (developer build)

See `docs/NATIVE_BUILD.md`. Install only into an isolated OBS test copy first.
Requires OBS 30+ APIs, compatible Qt6, and a matching 64-bit OBS SDK.

The main stream must be active with H.264/AAC. Disable Enhanced Broadcasting for
the test. Additional destinations reuse these encoders and the same scene/output
format; no separate bitrate or vertical composition. Each destination uses its
own upload bandwidth. Start one at a time and verify arrival on each platform.

Stopping the main OBS stream also stops all FDGCast secondary streams. Closing
the companion or losing its connection **does not stop ongoing native streams**;
the native dock includes a local stop button. Closing OBS stops all outputs.
Do not remove the plugin DLL while OBS is running.

## Stream Doctor: honest limits

Reports indicate what OBS measured, not an omniscient diagnosis. Rendering misses
do not prove which source or GPU process caused them. Network drops do not prove
whether your Wi-Fi, ISP, ingest route or destination server is responsible.
Simultaneous destination failures are a clue, not proof. There is no automatic
"fix", bitrate mutation, speed test, process killing or registry editing.

Two-second polling is near-real-time, not instantaneous. Incident entries are
rate-limited to once per issue per 30 seconds; sample counters still update.
Session history is bounded (120 samples and 300 incident entries), not permanent.
Export before closing. Chat is kept only in memory and is absent from reports.

## Hub integration

`docs/HUB_API.md` specifies **new, proposed endpoints**, not existing Hub behavior.
Implement them in your existing Hub backend before pairing. A separate integration
token must authenticate to a specific creator. No existing Discord login token is
repurposed. Fetch events manually; review and approve every report upload.

No chat, credentials, windows or source names are included in exported reports.
Reports do include timestamps, performance metrics and user-defined output names;
review those names before sharing. No analytics are added to public creator pages.
Do not sum platform viewers and call the result unique people.

## Security and data

- Listener binds to 127.0.0.1 only; not a LAN or Internet server.
- Per-run private dashboard capability is in the launch URL fragment, not HTTP
  query strings. It stays in browser session storage. Do not share that URL.
- API requests require bearer authorization; Host and Origin checks mitigate
  cross-site requests and DNS rebinding. Native bridge uses a different token.
- Windows secrets are encrypted with current-user DPAPI under
  `%LOCALAPPDATA%\ForgeCast\secrets.dpapi.json`. The app never returns saved tokens
  to normal chat/status payloads. Masked pairing/OBS setup endpoints are restricted
  to the authenticated local Companion. Other operating systems use session-only secrets.
- `%LOCALAPPDATA%\ForgeCast\config.json` contains nonsecret account metadata and
  ingest server URLs. Do not embed keys in server URL paths; use the key field.
- The native bridge capability is a local file, `bridge-token`, readable by this
  user's processes. Local software running as your user remains trusted.
- Platform tokens are sent only to their fixed official API endpoints. The Hub
  token is sent only to the explicitly configured HTTPS Hub; redirects are refused.
- There are no analytics trackers, ad SDKs, shell-execution endpoints or automatic
  updates. The launcher checks/install dependencies when run; review requirements.

## Tests

From this folder:

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

See `TEST_RESULTS.md` for the checks actually run in this environment.

## Sources and implementation references

- https://docs.obsproject.com/reference-outputs
- https://docs.obsproject.com/reference-frontend-api
- https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md
- https://dev.twitch.tv/docs/chat/send-receive-messages/
- https://dev.twitch.tv/docs/eventsub/eventsub-reference/
- https://dev.twitch.tv/docs/eventsub/handling-websocket-events/
- https://developers.google.com/youtube/v3/live/docs/liveChatMessages/list
- https://developers.google.com/youtube/v3/live/docs/liveChatMessages/insert

This is original source for this project, not a rebranded copy of Aitum. Before a
public release, select a distribution license compatible with OBS and all linked
dependencies, perform a security review and complete the live-platform test matrix.

