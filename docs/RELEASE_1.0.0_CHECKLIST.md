# FDGCast 1.0.0 release checklist

Target: stable Windows x64 release. Current candidate is 1.0.0 RC1; stable release acceptance remains outstanding.
This checklist supersedes the older release priorities in NEXT_STEPS.md.

## Included scope

- Combined Twitch, YouTube and Kick chat; receive-only Facebook, Instagram,
  Rumble and experimental TikTok chat. Meta delivery requires the separately
  deployed and configured Hub. A saved credential is not proof of chat delivery.
- Named multistream destinations with shared OBS video or 9:16 portrait crop/fit.
- Stream Doctor, Audio Guard, preflight checks, local diagnostics and backups.
- Saved paid Overlay Studio designs, independent revocable OBS URLs, chat,
  bounded emoji effects, alerts, text and manual goals. Core chat stays free.
- Clear connection status, noticeable events and optional chat badges.

## Next work, in order

- [ ] Deploy the Meta Hub changes with both chat flags disabled. Preserve the
  existing encryption key and pairing service; register callback/webhook URLs
  from META_CHAT_DESKTOP.md and META-CHAT-SETUP.md in the Hub handoff.
- [ ] Verify Meta permissions, supported Graph version and public access/review
  requirements in the application dashboard, then enable controlled testing.
- [ ] Check an actual comment from each supported platform in the OBS dock.
  Include Facebook Page and Instagram professional-account broadcasts, and a
  creator's Rumble private API connection. Record pass/fail; not assumed passed.
- [ ] Run an extended stream with temporary network loss, restart and reconnect.
  Confirm no duplicate messages, wrong-account comments or exposed credentials.
- [ ] Check OBS chat resizing, intentional scrollback, event visibility and badge
  toggle on the installed Windows build, including a small dock layout.
- [ ] Verify overlay free/paid access against the deployed Hub, revocation,
  saved design URLs, hidden-source pause and acceptable OBS resource use.
- [ ] Verify viewer picture/audio on selected destinations, Start/Stop All,
  recording, Audio Guard and Stream Doctor using the real OBS setup.
- [ ] Test installation over the previous preview: pairing, protected keys,
  saved designs and preferences survive; uninstall/reinstall guidance is clear.
- [ ] Resolve failures, run the full Windows build and regression checks, then
  prepare 1.0.0 notes, package version, installer hash and matching update feed.
- [ ] Publish the stable installer and update metadata together after acceptance.

Automated baseline: the previous Meta preview passed 227 Python tests, Windows
native compilation, Chromium UI checks, packaged dependency checks, desktop
startup and installer smoke checks (run 39058290174). That evidence applies to
that preview; new changes require their own validation.

## After 1.0.0

Animated ending credits, independently composed vertical scenes, deeper hardware
profiling, advanced automation and team controls remain future work. They are
not required to finish this release. TikTok remains explicitly experimental;
unsupported platform sending/moderation is not advertised.
