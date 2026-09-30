# Phase 1 source checkpoint — 2026-09-30

No installer or Windows build has been generated for this checkpoint. The published 0.4.0 preview remains the last built version.

Implemented in source:
- Automatically sync Hub accounts at startup and every 60 seconds; an account error does not prevent other platforms from connecting.
- Discover YouTube's active chat after pairing before going live, and rediscover after a broadcast ends. Reset expired page cursors and slow retries for quota/rate limits.
- Persist linked chat credentials through the existing vault and honor explicit local disconnects until manual Sync.
- Verify/recreate Kick's official chat webhook subscription. Distinguish subscription readiness from actual message delivery. Filter relay messages to the linked broadcaster and skip malformed payloads without blocking later messages.
- Expose readable API errors with safe HTTP/reason codes and connection details, excluding raw error responses/tokens.
- Keep Combined Events for supported audience activity. Scene changes, app operations and diagnostic incidents remain in their respective companion/Doctor views.
- Arrange Docks climbs intermediate widget parents, uses OBS's real main window, clears floating state, enables normal docking, retries initialization, logs presence/fallbacks, and marks success only after arrangement completes.
- Stage deterministic username colors, creator identity/avatar metadata, Twitch/Kick emote fragments and a bounded media proxy for the next presentation pass. Existing UI still renders text.

Validation: 59 Python tests pass, including seven new regressions for broadcast discovery, per-platform failure isolation, Kick subscription readiness, relay channel filtering/cursor handling, safe API reasons/media hosts and moderation of emote fragments. Python compilation passes. Native changes require the deferred Windows CI compile and clean-install OBS test. No live API credentials or broadcaster sessions were used.

Next pass: chat icons/name truncation/avatar and emote rendering in both native and companion views; Start All/Stop All and per-destination enable controls; additional audience event subscriptions with Hub permissions; manual clean-install docking and live YouTube/Kick tests. YouTube custom/member emote image availability must be checked against the supported API response. Audio Guard, notifications, history, vertical composition and overlays are later phases.

Engine inspection: each secondary destination owns one rtmp_custom service and one rtmp_output. Its video encoder and first audio encoder are references to the main stream's existing H.264/AAC encoders. Companion sends control/telemetry JSON over authenticated loopback, not media. OBS continues secondary outputs if Companion closes, and stops them when the main stream stops. OBS reconnect settings are 10 retries at 2-second intervals. No independent scaling/encoding path exists. Upload is required per destination; no performance comparison has been measured.

## Interface checkpoint — 2026-09-30

Chat presentation is now implemented in the native OBS dock and Companion: local Twitch/YouTube/Kick icons, deterministic username colors, truncated names with full-name hover, creator markers and available creator avatars, readable original-channel labels, and native Twitch/Kick emote images. GIF playback uses Qt in the dock and normal image rendering in Companion. Companion falls back to emote text when an image fails. Unicode emoji remain text; YouTube custom/member emote images and third-party emotes are not implemented.

Multistream now offers START ALL / STOP ALL and persistent per-destination checkboxes. START ALL explicitly starts OBS main streaming, waits up to 60 seconds for it to become active, then starts the selected secondary outputs using the existing shared encoders. STOP ALL stops main and secondary streams and cancels pending bulk starts. The separate Control dock emergency button still stops only secondary streams. Checkbox changes select the next bulk start and do not stop an already-live output. Individual start/stop controls remain.

Health states show green LIVE, yellow CONNECTING/STOPPING or RECONNECTING, red ERROR, and gray OFFLINE. Safe native result codes become readable per-destination error messages. Unexpectedly stopped native outputs have a visible error state. Action feedback has its own label so telemetry updates do not immediately erase failures. Supported audience events also appear in Companion, without adding a tab.

Validation: all 68 Python tests pass, including bulk selection, key privacy, checkbox persistence, missing-key atomicity, authenticated dock routes, readable output errors and icon routing. Python compilation and JavaScript syntax checks pass. Visual QA could not execute because the installed Playwright package has no browser binary. Native C++ compilation, Windows/OBS visual testing, animation checks and live platform validation remain deferred with the full build. The existing installer has not changed. CI is skipped for this checkpoint.

## Audio Guard checkpoint — 2026-09-30

Audio Guard is implemented in source as a free feature within the existing Stream Doctor dock and Companion tab. Select a microphone and optional game/desktop audio source once in settings. Sources are identified by OBS UUID, so renamed sources remain selected; deleted/replaced sources produce a visible warning.

The plugin reports mute, activity, source volume, monitor-only state, audio mixer flags and recent native input meter activity. Only selected sources get meter callbacks (maximum eight); audio samples/recordings are not transported or saved. The actual first stream audio encoder's mixer index is read while live, matching FDGCast's shared secondary audio encoder. No Track 1 assumption is used for live routing diagnosis. The preflight check explicitly reports routing as unverified until the active encoder is available.

Detection: prolonged mute, inactive/missing expected source, zero source volume, Monitor Only, exclusion from the actual stream track, prolonged lack of signal and missing meter updates. No signal does not prove device disconnection or verify viewer playback. Quiet scenes are configurable exact names or conventional prefixes such as BRB - Coffee; alerts run only while streaming. Timers reset after telemetry gaps/scene pauses and do not falsely record those pauses as recovery.

Controls: UNMUTE, FIX STREAM ROUTING, SNOOZE 10 MINUTES and I KNOW. Explicit routing fixes OR the actual stream track into the source mask, preserving all other tracks, and change Monitor Only to Monitor and Output if needed. No automatic changes or hard streaming blocks. Source/track identities are rechecked in OBS when each command executes.

Muted source timing: 30-second dock warning, 60-second Windows notification, optional notification sound at two minutes, and a five-minute reminder. Silence defaults to 90 seconds and is configurable. Routing warnings use a short three-second settling interval and notification at ten seconds. Snooze resumes with one current notice, not a backlog. Acknowledgement lasts until that condition clears. Windows notification code uses the existing FDGCast app identity; installer shortcuts now register that identity. Windows Do Not Disturb/notification settings may suppress display. Notification submission and failures are recorded separately from requested alerts.

Audio incidents, recoveries, pauses and fix requests/results are saved locally in bounded JSONL history and shown in Companion. Shared reports include counts with no audio source identities. If history saving fails, monitoring continues and Companion shows the storage error.

Validation: 85 local Python tests pass, including mute thresholds, actual non-default track selection, quiet-scene behavior, telemetry loss, acknowledgement/snooze, source deletion, silence/meter distinctions, persistence/report privacy, safe toast XML encoding, API selection/authentication and preflight uncertainty. Python compilation and JavaScript syntax pass. Native compilation, Windows notifications, actual microphone/Focusrite tests and visual OBS validation await the deferred Windows build. Existing installed copies do not yet contain these source changes.

## Pairing clarity and Companion startup checkpoint

- Saved Hub pairing code remains in its masked local form with Show/Hide. A browser-authenticated, no-store endpoint restores it after app restarts; normal state, native IPC and reports exclude it.
- Hub pairing status reports Connected only after an authenticated account-sync response; failed checks show attention and retry automatically.
- OBS opens the installed Windows Companion once at plugin startup if its local service is absent. Installer records its executable path; no streaming outputs are started. Opening the app from Control also retries startup.
- Windows desktop mutex prevents simultaneous app launches from rotating bridge credentials or spawning duplicate windows. Closing Companion does not cause an automatic restart loop.
- 87 Python tests pass; Python compilation and JS syntax checks pass. Registry launch, single-instance behavior and UI rendering still require the deferred Windows/OBS build and live validation.

Next: destination-specific Stream Doctor incidents and recovery history, followed by the combined session timeline and copyable diagnostic report.

## Core release: Doctor, preflight, history and engine inspection

Scope stops at roadmap Phase 4. Vertical streaming and native overlays are deferred to a later release.

- Destination health now records reconnects, unexpected stops, failed starts and network-frame drops. Healthy destinations are described only as locally active with no new network drops; viewer playback is never claimed. Multiple problems produce a possible shared-issue diagnosis.
- Windows Doctor notifications support a live-only setting, suppress intentional stops and stale queued alerts, and group simultaneous destination warnings. Recovery requires five seconds of stable samples. Telemetry gaps close measurement continuity without inventing recovery duration.
- Native main output counters supplement secondary telemetry; frame/encoder counters still require OBS WebSocket. Doctor can show destination/audio health when WebSocket statistics are unavailable.
- Local bounded stream history records sessions, controls, incidents, recoveries, telemetry gaps and Audio Guard entries. Restarting an unfinished session marks its final state unknown. Frame lag has separate stable-counter recovery and lost-statistics handling. Disk-write failure does not stop monitoring.
- Existing Doctor page gains destination health, session filter, combined timeline and Copy Diagnostic Report. Clipboard failure exposes selectable text. Shared JSON history omits source identities, arbitrary error details, chat, URLs and credentials. User-entered names in local/text reports need review before sharing.
- Preflight combines OBS/plugin, selected audio, routing, destination keys and chat state. Audio fixes require a click. Go Live Anyway retains explicit broadcast confirmation and does not hard-block the user. Encoder compatibility/delivery remain unverified offline.
- `docs/ENGINE_VALIDATION.md` documents encoder reuse, independent output upload, service ownership, reconnects, Companion/OBS failure behavior, Windows acceptance tests and a matched FDGCast → Aitum → FDGCast benchmark. Source inspection is complete; the actual benchmark and native failure tests cannot run in this environment.
- 108 Python tests pass, plus Python compilation and JavaScript syntax checks. Native compilation, Windows/OBS integration, toast display, visual UI checks and platform playback still require the deferred build. No installer or CI build was triggered.

## 0.5.0 Preview release quality pass

- Review fixed automatic restoration of saved OBS WebSocket settings, with bounded reconnect retries after OBS restarts. It also records known output-start failure codes in the timeline when no native output was created.
- 110 local Python tests pass; Python and JavaScript compile/syntax checks pass.
- Windows CI now runs Python checks, Chromium Companion UI checks and screenshot capture, native compilation, packaged service/window/icon/focus/duplicate-instance smoke tests, and installed module/registered Companion-path checks.
- The installer build is now authorized. Platform playback, OBS live-output/Audio Guard integration, full-screen notification display and the controlled performance benchmark remain manual acceptance work.

## 0.5.1 Preview: compact, flexible OBS docks

- Removed repeated dock headings and persistent explanatory footers. Chat connection states now use short labels with full details on hover; reply feedback appears only while sending or on failure. Chat origin channel remains visible by default, beside the username.
- Per-dock ⋮ menus persist compact spacing, 11/13/15/17px text, connection-status visibility and extra-control visibility. Chat also permits hiding its composer or origin labels; origins remain available in username hover details.
- Doctor shows a compact audio state, concise destination/frame warnings and conditional audio fix button. Full evidence is available on hover or by opening Companion; Snooze/I Know/Open Companion remain in its menu. Expanded controls/details remain selectable.
- Multistream defaults to Start All/Stop All and a flexible destination list; add/remove and selected-output controls stay available in the menu, or can be shown inline.
- Scrollable content removes the old stacked-control and 95px-list height floor. Dock content can shrink to 100×60px with scrolling when necessary; OBS title bars and neighboring docks still affect the overall layout limit.
- Fixed stale Events status after reconnect, and marks Multistream rows UNKNOWN while Companion is offline. Preferences persist independently of OBS's dock positions.
- Python tests and JS checks retain coverage; Windows compilation/package tests validate the release. Live docking/resize acceptance still needs OBS.
