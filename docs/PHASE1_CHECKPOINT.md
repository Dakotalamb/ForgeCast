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
