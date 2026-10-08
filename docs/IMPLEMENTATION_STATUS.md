# Scope against the October 8 offering roadmap

| Area | Implemented locally | Remaining dependency or scope |
|---|---|---|
| Combined chat | Three adapters; origin/platform labels; filters; emotes; badges/replies; pause; customizable rendering; hashed restart dedup | Real extended outage/reconnect tests; deployment and live verification of the patched Hub refresh/subscription handling; avatar lookup depends on platform availability |
| Replies/moderation | Single/all-connected send; feedback; mention/Twitch reply; Twitch/YouTube delete/timeout/ban; scoped account history/copy/profile | Kick moderation; independently authorized collaborator channels; external role verification on real accounts |
| Events | Default follow/redeem/raid; optional available subs/gifts/Bits/YouTube paid/membership categories; toggle/merge/test/ack/bounded history | Actual delivery tests; third-party tips; platform-specific Kick audience events |
| Multistream | Shared main H.264/AAC; Start/Stop All/individual; presets; per-output health; masked keys; upload calculator | Independent encoders/resolutions/audio, vertical canvas and cloud relay |
| Stream Doctor | Sustained sensitivity profiles; frame classes; health history; optional Windows/sound alerts | Custom thresholds, root-cause profiling beyond measured OBS counters |
| Audio Guard | Expected sources; mute/silence/meter/routing; scenes; custom WAV; optional near-clipping and chosen VOD track | Final viewer/VOD playback verification; full guided recording/listen workflow |
| Preflight | App/docks/OBS/platform/dest/audio/recording/storage/event checks; native modal and app fix navigation | Per-check saved dismissals; capture verification |
| Installation | Windows installer/icons; desktop single instance; OBS auto-launch; saved pairing; update notices/reinstall guidance | Full multi-OBS-version matrix; signed distribution and automated rollback |
| Docks | Existing small minima; spacing/font/filter/preferences/reset; existing arrange preset; optional Hub dock | Real OBS UI/accessibility tests; additional layout presets |
| Help | Search, first stream, troubleshooting, official links, budget estimate and optional guidance | Hardware profiling and tailored settings profiles; never silently applied |
| Hub scheduling | Reads compatible events and selected event context | Recovered Hub 2.13.3 source now returns event IDs, statuses and accepted participants; ZIP must be deployed. Broader scheduling improvements remain separate |
| Hub in OBS | Optional Today’s Events dock with local times/RSVPs/game/instructions/links | Verified live participant state, title/category updates, delegated chats |
| Discord | Existing product integration remains external | Audit and improve its deployed queue/worker from its current source |
| Twitch extension | Existing released extension remains external | Setup/empty/error copy and payload updates in its current source |
| Overlay | Local transparent read-only, all/recent or selected highlight, duration, themes/text/spacing, preview via Browser Source, sequenced highlight queue, moderation removal | Public hosting |
| Integrations | Existing OBS WebSocket; setup guidance and authenticated local action interface | Dedicated Stream Deck/Streamer.bot/Crowd Control adapters and verified use cases |
| Support | Diagnostics preview/export/confirmed upload; issues/notes/known issues/version | Dedicated in-app report form/Hub feature request intake |
| Summaries | Locally observed durations/destinations/incidents/warnings/chat/event counts; export | Full platform analytics and team/sponsor reporting |
| Business offering | Free local features; no payment gates added | Paid themes/team/cloud/AI/billing require service implementation and cost decisions |

This is a preview implementation, not a claim that every proposed service is
finished or real platform behavior has passed testing. The handoff separates local implementation, the prepared Hub integration ZIP,
required deployment/live verification, and later service features.
