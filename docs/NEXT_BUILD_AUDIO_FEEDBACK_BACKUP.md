# FDGCast 0.8.0: audio test, feedback and preference backup

Originally prepared on next/audio-feedback-backup and now included in the tested 0.8.0 Preview installer. No Hub source was modified. See RELEASE_0.8.0.md for current build evidence.

Companion Help now offers a 20-second OBS recording test, finishing early,
opening its returned local media file in Windows, and a listening checklist.
Existing recording or streaming blocks the test. It only stops its own recording
on the same WebSocket connection; external stop/reconnect revokes ownership.
Closing Companion attempts to finish its own recording. Unconfirmed/interrupted
operations require checking OBS manually. Recording uses existing OBS settings
and its folder, and cannot establish platform or VOD playback quality.

The feedback form previews problem reports or feature requests. Diagnostics
are optional; known credentials and URLs are redacted. Review user text/output
names for private details. Download without uploading, or explicitly send the
exact preview to the existing private Hub /api/forgecast/v1/reports endpoint.
Successful submission clears that preview; no delivery-to-staff or response-time
promise is made. No new backend form, email or automatic message is introduced.

Preference backups use a bounded versioned allowlist. Include supported Companion
preferences and destination names, exclude all tokens, stream keys/server URLs,
audio source assignments, custom WAVs and OBS dock layout. Restore only with OBS
closed. Validate completely before atomic write; preserve existing keys
and destinations. New destination names are unchecked placeholders requiring
server/key setup. Restart Companion and sync accounts after restoring event choices.

Validation: 180 Python tests passed, including 14 new ownership, restart, privacy,
permission, confirmation and restore-failure checks. JavaScript syntax passed.
Windows behavior and Chromium verification passed in run
https://github.com/Dakotalamb/ForgeCast/actions/runs/37863356654
including the existing interface and simulated recording controls, feedback
preview/XSS/confirmation/edit reset, backup review/restore and mobile overflow. These additions were absent from 0.7.0; they are included in the 0.8.0 Preview installer, whose expanded suite passes 194 Python tests and Windows/browser/package checks.
