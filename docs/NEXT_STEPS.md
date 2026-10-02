# Next planned feature: update notifications

Saved October 1, 2026. Deferred at the user's request; do not implement until work resumes.

Add an update checker to the desktop Companion and a small update notice in the OBS Control dock.

- Check on Companion startup and once daily against a small release manifest hosted on the FDG website.
- Compare installed and latest versions; show both in Companion.
- When a newer release exists, offer View changes, Download, and Later.
- Show a small badge/notice in the OBS Control dock and a banner in Companion.
- Persist Later so the same update does not repeatedly interrupt the user.
- Download uses the approved installer link; installation remains a user action.
- Never install or restart automatically, especially during a stream.
- Installing over the current release preserves existing settings.

Current shipped version: 0.5.5 Preview. The next version number is not yet assigned. Coordinate the website release manifest and public download links before shipping the checker.
