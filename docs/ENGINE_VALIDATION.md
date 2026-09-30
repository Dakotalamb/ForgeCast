# FDGCast core release: engine inspection and validation

Scope: Stream Doctor, preflight, session history, reliability and measurement. Vertical production and native overlays are deferred. Source checkpoint only; no new Windows installer or native compilation is claimed.

## What the source does

`native/forgecast.cpp` creates one OBS `rtmp_output` and `rtmp_custom` service per secondary destination, capped at eight, in addition to OBS's main output. Each secondary receives the **same encoder objects** retrieved from the main output: video index zero and audio index zero. FDGCast does not call encoder-create for those secondary outputs, render another canvas, scale frames, or send encoded media through Companion. H.264 and AAC are required; independent encoding and Enhanced Broadcasting are unsupported.

Each output has its own connection, network counters, bytes, start/stop lifecycle and OBS reconnect configuration (10 retries, two-second delay). Native code owns services/outputs and releases their references on removal or unload. Start All waits up to 60 ticks for the main stream to become active; a secondary start exceeding 30 ticks is force-stopped before retry. The timer runs at one second; blocked OBS UI can extend wall-clock timing.

Encoded data reuse reduces duplicated encoding work in this implementation. It does **not** reduce upload traffic: each destination receives its own copy. Approximate aggregate upload is the per-destination video-plus-audio bitrate multiplied by destination count, plus protocol overhead. Actual upload, NVENC utilization and comparative performance have not been measured here.

Companion sends control/configuration over authenticated loopback HTTP. Stream keys are included only in authenticated native start commands; normal public state and reports exclude them. Chat and diagnostic payloads are bounded. Native commands expire after ten seconds. Companion closing leaves already-active native outputs running while OBS's main stream remains active; controls/chat/Doctor alerts become unavailable. If the main stream stops, native code stops secondary streams. OBS closing unloads the module and its outputs. Companion retains saved history and marks missing telemetry as unknown, never proof that viewers lost the stream. Restarting Companion closes an unfinished journal session as interrupted, without inventing its final state.

OBS native telemetry supplies main/secondary active/reconnect/network counters and bytes, plus selected-source audio meters. OBS WebSocket supplies rendering/encoding counters and CPU/FPS. These measure symptoms, not exact root cause or actual viewer playback. A live output is not proof that a platform is publicly visible. Byte-delta bitrate is observed throughput, not measured available upload.

## Local automated checks

Run `python -m unittest discover -s tests -q`, `python -m compileall -q forgecast launcher.py`, and `node --check web/app.js` from the repository root. Tests cover normal/intentional stops, individual/multiple destination degradation, stable recovery, stale telemetry, interrupted history, privacy, frame counter recovery, Audio Guard timers, command expiry and token separation. Native OBS and Windows tests remain outstanding.

## Windows/OBS acceptance checks after the deferred build

1. Clean install: launch OBS without Companion open; exactly one desktop app starts and docks attach. Launch the app twice and launch OBS twice without duplicate bridge instances. Restart both; pairing code remains masked and Connected appears after a successful Hub check. Test failed Hub checks and code replacement.
2. Stream to three test destinations. Use a platform's test/unlisted mode where available. Verify each platform dashboard and viewer playback independently. Start All and Stop All; test destination checkboxes and individual stops. An intentional stop must not raise a disconnected alert.
3. Disrupt only one destination route, then restore it. Doctor should report that destination, identify other locally active outputs, and record a stable recovery with observed duration. Repeat with shared network disruption; diagnosis should state a possible shared issue, not assert the ISP/GPU caused it.
4. Test a bad key, unreachable ingest, start timeout, retry exhaustion and reconnect. Messages must be readable and never include keys. Verify new-session counters and byte resets do not produce negative bitrate or false drop counts.
5. Close Companion while streaming. Existing outputs should remain active; verify on platform dashboards. Reopen it; telemetry and controls resume. A gap cannot produce an exact downtime claim. Test a stopped OBS process, OBS restart, bridge port conflict and Companion crash/restart. No automatic stream start on restart.
6. Audio: selected mic muted/unmuted, quiet scenes, missing source, silent input, monitoring-only, stream Track 1 and a different track. Fix only after an explicit click. Other audio tracks must remain enabled. Exercise Snooze and I Know.
7. Notifications: installed shortcut identity, silent warning, optional Audio Guard sound, disabled setting, live-only behavior, Windows Do Not Disturb and full-screen games. Submission is not proof Windows displayed a popup. Stop or recover before a queued alert is delivered; stale alerts should not appear.
8. Timeline/report: restart Companion, inspect interrupted session, select older sessions, copy and download reports, check history write failure. Review user-entered names before sharing text reports. Shared JSON timeline excludes source identities and arbitrary native error text.
9. Arrange docks on a clean profile, then saved custom layouts at different DPI. Verify left/right/bottom docking and width reduction. Test native Twitch/Kick/YouTube chat and emotes after authorized connections; Google approval is still an external dependency.

## Controlled comparison: FDGCast → Aitum → FDGCast

Use the same OBS version, plugins other than the one under comparison, scene collection, game/benchmark replay, encoder, resolution, FPS, bitrate, destinations and network. Restart OBS between runs; record exact plugin versions. Avoid running both multistream plugins together. Warm up five minutes, measure 20 minutes, then repeat the first condition. Record Windows/OBS observations, not estimates.

Capture OBS CPU, total CPU, GPU/encoder utilization, encoding/render missed frames, each output's dropped frames and observed bitrate, reconnect count/duration, encoder sessions if your NVIDIA tooling exposes them, and platform playback verification. Export reports and preserve OBS logs privately. A single promising run cannot establish a performance claim.

Suggested results CSV columns: run_id,plugin,plugin_version,obs_version,duration_seconds,destinations,video_kbps,audio_kbps,obs_cpu_average,system_cpu_average,gpu_average,encoder_utilization_average,render_missed,encode_missed,network_dropped_main,network_dropped_secondary,reconnect_count,reconnect_seconds,playback_verified,notes.

Do not advertise lower resource usage until repeated matched runs support it. This environment cannot execute that Windows/OBS benchmark.
