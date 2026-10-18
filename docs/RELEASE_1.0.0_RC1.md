# FDGCast 1.0.0 release candidates

Current candidate: **1.0.0 RC4**, with draw-on-horizontal camera crops, prominent default-on scene following,
a dedicated Vertical Studio tab, sampled
live-source previews, layout presets and saved per-scene native composition.
See [Vertical Studio setup and validation](VERTICAL_STUDIO.md). The sections below
describe the earlier RC1/RC2 baseline; RC3 adds the separate scene layout editor.

## RC1 baseline

Windows x64, OBS Studio 32.2.2. Release candidate for acceptance testing;
the hosted stable update feed is unchanged.

## Portrait video

In Destinations, select a platform, enter its stream key and choose Picture format:

| Choice | Picture | Encoding |
| --- | --- | --- |
| Same as OBS | Current main program and resolution | Reuses main H.264 video |
| Vertical · fill screen | Center crop filling 9:16; sides of wide scenes disappear | Separate 720 × 1280 H.264, 4500 kbps |
| Vertical · show whole picture | Full scene; wide pictures have black space above/below | Separate 720 × 1280 H.264, 4500 kbps |

All choices follow main scene changes/transitions and use the main AAC audio.
Portrait video keeps the OBS frame rate. Start All starts the main stream and
checked destinations; stop the destination before editing its picture format.
The native Add stream dialog has the same choices. Existing destinations retain
their main picture unless explicitly edited.

Vertical output requires additional encoder capacity. Destinations with the same
portrait framing share one portrait encoder; fill and whole-picture modes use
separate encoders. Inactive portrait outputs release their render view and
encoder after stopping. No platform eligibility, server or stream key is supplied
by selecting vertical. Check framing, picture, audio and encoding lag on the
actual platform before publishing.

This version reframes the main program. Separate vertical scene composition,
camera/game repositioning, independent portrait overlays and arbitrary per-output
resolution/bitrate controls are future work. The Companion framing illustration
is explanatory, not a live video preview. Overlays already in the main program
are cropped or fitted with the rest of the picture.

## Usability

- Visible framing guidance and an illustration next to the picture selector.
- Clear destination format labels; edit mode has Save changes and Cancel editing.
- Destination save confirmation and keyboard focus indicators.
- Tooltips explain streaming controls, paid overlay links, link replacement,
  effect limits, manual goal progress, platform filters and account connections.
- All seven chats appear before discovery; pairing changes clear old Meta status.
- Updated help for vertical video, Meta chat and dock Options controls.

## Acceptance before stable release

Automated checks cover framing geometry, format validation, queued start
commands, existing regression behavior and browser guidance. Windows native
compilation, interface and installer checks run in the release workflow.
They cannot establish actual creator GPU headroom or end-to-end platform delivery.

Use the 1.0.0 checklist for real OBS/broadcast, Meta Hub deployment, overlay
entitlement and upgrade acceptance. Core chat remains free; Overlay Studio live
feeds retain the existing Hub entitlement requirement. TikTok remains experimental.
Close OBS and Companion before installing. Saved pairing, keys and designs remain
in the existing data directory. No stable release or website deployment is performed
by building this candidate.

## RC2 follow-up

The current candidate is 1.0.0 RC2. It requires the native module to advertise
portrait support before starting a vertical destination. An older module gives
a clear update instruction instead of silently streaming landscape video.
Stop controls remain available. Native capabilities refresh on every poll.

Unavailable buttons use the normal disabled cursor. Only an action actually
in progress uses a progress cursor and an accessible busy state.

### RC2 automated validation and installer

232 Python tests passed. Windows portrait framing tests, native OBS 32.2.2
compilation, all three Chromium interface suites, packaged service/dependency
checks, desktop startup and installer placement checks passed in:
https://github.com/Dakotalamb/ForgeCast/actions/runs/39083642640

Tested source: c5b808d35b33f592f07bf131ee4b2a0b698e7032.
Installer: `FDGCast-1.0.0-rc.2-win-x64-setup.exe`.
Size: 22677066 bytes.
SHA-256: `a79ac3bcf10ddf09461e3b6f13e998129605567b7528b07760f63bbe4499aa3d`.

Stable 1.0.0 and the hosted update feed were not published. Actual OBS portrait
playback, platform chat delivery, deployed Hub/Meta setup and real upgrade
acceptance remain outstanding. Automated compilation is not a live video test.
