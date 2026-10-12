# Website builder handoff — FDGCast 0.9.0 Preview

No Hub source changes are included in the FDGCast repository. Integrate the following
into the website thread's current source, preserving its newer unrelated work.

## Required paid overlay access

Add a literal boolean `entitlements.fdgcast_overlays` to the existing authenticated
`GET /api/forgecast/v1/connections` response. Keep every existing account field and
refresh behavior. Compute access from the integration token owner's authoritative
shared entitlement service. Do not accept a client-supplied plan/flag.

Recommended mapping: eligible Supporter access, including official FDG complimentary
members, administrators and valid grants; eligible future Business plans may grant
the same flag without enabling paid Business checkout. Blocked accounts, revoked
pairings and ineligible subscriptions must not grant access. Return false on access
loss. The desktop does not set pricing or create checkout sessions.

The desktop gates both legacy chat overlays and saved-design live feeds. Free design
previews contain only labelled sample data. Verified access has at most fifteen
minutes of in-memory connectivity grace; an explicit false denies immediately, and
restart needs a fresh Hub verification. Saved designs are retained when access ends.

Test paired free/paid/complimentary/admin accounts, blocked accounts, cancellation,
expired access, revoked tokens and transient failures. Confirm that access changes
do not disconnect working Twitch/YouTube/Kick chats.

## Website publication after installer validation

1. Host `FDGCast-0.9.0-preview-win-x64-setup.exe` at
   `/downloads/FDGCast-0.9.0-preview-win-x64-setup.exe`.
2. Verify the hosted size and SHA-256 against the final tested build.
3. Only then change `/fdgcast/releases/latest.json` to version `0.9.0-preview`,
   platform `windows-x64`, the above relative download URL, schema version 1,
   release notes and the actual final SHA-256. Do not reuse the 0.8.0 hash.
4. Update the FDGCast download page and changelog using `RELEASE_0.9.0.md`.
5. Keep the label Preview and target Windows x64 / OBS 32.2.2. Full release is 1.0.0.
6. Tell users to close OBS and Companion before upgrading. Settings and pairing persist.

This handoff does not contain a final installer hash yet: the Windows build remains
blocked on authorized public repository upload. Never advertise the installer until
its build, browser and packaged-dependency checks pass.

## Platform notes

TikTok and Rumble chat are desktop readers; no new OAuth callbacks, Hub client
secrets or webhook routes are required for them. Rumble's private API URL remains in
the desktop vault. TikTok uses an unofficial third-party signing service and is
experimental. Facebook and the other new manual destinations send video only;
combined chat is not automatically connected. Keep existing Kick webhook and
YouTube refresh fixes intact.
