# Vertical Studio

Open the dedicated Vertical Studio tab in Companion. Connect OBS WebSocket in
Connections, then refresh OBS sources. No extra OBS docks, camera captures or
Browser Sources are created.

1. Leave **Follow horizontal scene — ON** enabled (the default). It is prominent
   at the top; switch it off explicitly to choose a different scene to edit.
2. Choose a layout such as Camera top, Camera bottom or Camera corner.
3. Click **Mark camera area**, then drag a box around your camera on the large
   horizontal preview. The selected picture uses that part of the horizontal
   scene. Move the box or resize its bottom-right corner to adjust the crop.
4. Drag/resize the result in the vertical preview to place it. **Add crop** adds
   another region from the same horizontal picture. **Use whole picture** clears
   the selected crop. No separate camera selection is needed.
5. Save scene layout. Saved layouts follow OBS scenes. Unsaved edits only change
   the preview and pause editor following until saved or reverted.
6. Choose **OBS main stream · [your service]** or another destination and click
   Use Vertical Studio. In Destinations, the main stream has its own picture
   selector and **Apply main stream picture** button. Wait for **Applied:
   Vertical Studio** before starting. No duplicate account or stream key needed.
7. Start OBS streaming normally, or use Start All with checked destinations.
   The main stream can be vertical while added destinations send horizontal,
   or the main stream can stay horizontal while other destinations send vertical.
   Each destination sends one picture. Stop the main stream (including connection,
   delay and reconnect activity) before changing its picture.

Main stream selection is saved by the native plugin on this PC. It applies to
whichever service is configured in OBS, rather than hardcoding Twitch. The
initial vertical main-stream path requires standard RTMP/RTMPS, H.264/AAC and
Enhanced Broadcasting / multitrack video off. Open Companion first so saved
layouts sync. If vertical setup fails, video is detached before OBS starts so
it cannot silently broadcast the horizontal picture instead. Return to Horizontal
in Destinations to restore normal behavior. Main service, credentials, audio/VOD
tracks, main canvas and recording settings are not changed.

Horizontal destinations retain the original OBS scene encoder when the main
stream is vertical. Vertical Studio destinations share the vertical main encoder;
there is no second Studio encoder for identical layouts. OBS restores the original
main video binding after the stream stops. A portrait stream still uses rendering
and encoding resources. Cropping the existing scene avoids another capture device,
but no GPU reduction or hardware benchmark is claimed.

The optional Advanced picture controls retain source selection, exact pixel
positions/sizes, zoom, mirroring, visibility and layer ordering. Selecting an
existing source still reuses it; it does not create another camera device.

Crops store normalized coordinates and follow the horizontal scene dimensions.
Only content present in the horizontal picture can be extracted. A small camera
area is enlarged with that picture's available detail; direct source selection
in Advanced remains an option for independent camera framing/detail. Cropping
avoids extra camera-source setup and extra camera preview requests, but lower
GPU use is not guaranteed: vertical rendering and encoding still have a cost.

Both previews use sampled images from OBS, defaulting to one update per second.
The OBS preview shows the current live scene; the vertical preview composes the
selected scene's live source images with the draft framing. This is not an
encoded-output monitor. Preview frames are local, authenticated, no-store and
never saved, included in diagnostics or uploaded. Pause or hide the tab to stop
capture requests. Broadcast rendering keeps the OBS frame rate.

Saved Studio layouts render natively at 720 × 1280 / H.264 4500 kbps, reuse main
AAC audio and share one Studio encoder across destinations. Source UUIDs keep
layouts stable through renames. Removed sources must be replaced. At most four
picture layers and 128 scene-specific layouts plus a default are supported.

The renderer selects layouts from OBS's active program scene on the render
thread; editor polling is not responsible for broadcast scene following.
Full-scene pictures contain the main transition. Individually arranged source
pictures switch at the active-scene boundary; this version does not reproduce
every OBS stinger/transition separately for each custom layer. Camera sources
are reused and kept active only while required by the running Studio view.

Blurred backgrounds, automatic face tracking, arbitrary rotations/masks and
separate vertical audio mixing are not included. The original OBS composition
is not edited. Check actual platform framing and playback before public use.

## RC3 build validation

Six focused backend checks passed locally. The Windows release workflow passed
238 Python tests, native framing checks and OBS 32.2.2 compilation, the existing
browser suites and the targeted Vertical Studio editor check, packaged startup
and installer placement checks. Desktop/mobile screenshots were reviewed.
The editor check covers source composition, camera zoom/mirroring, saving, scene
following, unsaved-edit protection, pausing and inactive-tab preview behavior.
No real creator broadcast or GPU resource measurement was performed.

Build: https://github.com/Dakotalamb/ForgeCast/actions/runs/39085323798
Source: b9456f69453ceef9c9ea3f0a9212037608714f5d.
Installer: `FDGCast-1.0.0-rc.3-win-x64-setup.exe`.
Size: 22697350 bytes.
SHA-256: `480fdf0e69134b16dea521b71342aaeabffaa005574c6fda2cdc10a17e9cfd81`.
Stable 1.0.0 and the hosted update feed remain unchanged.

## RC4: simpler horizontal-scene crops

Current candidate is 1.0.0 RC4. Camera regions can be drawn, moved and resized on
the horizontal preview, then arranged vertically. Follow horizontal scene is on
by default, prominently labeled ON/OFF; choosing a scene cannot silently disable
it. Source selection and detailed controls are optional, collapsed by default.
Crop previews use the horizontal snapshot without separate camera requests.
Native crop capability prevents older modules silently ignoring crop settings.

Seven focused backend checks passed locally. Windows workflow 39086614304 passed
239 Python tests, native compilation, browser checks including actual crop
drawing/default follow/hidden advanced controls, packaged startup and installer
checks. The desktop screenshot was reviewed. Actual creator broadcast playback
and GPU savings were not measured.

Build: https://github.com/Dakotalamb/ForgeCast/actions/runs/39086614304
Source: 1825042e20d2d89777fca95eb8caf6e9705938d5.
Installer: `FDGCast-1.0.0-rc.4-win-x64-setup.exe`. Size: 22699593 bytes.
SHA-256: `07c137c6787ece5ffd7de5e993638fa1a462c7b2df3d73a28a388988c5c94b01`.


## RC5 validation scope

RC5 adds the main output picture selector and native pre-start video binding.
Focused tests cover ownership/restoration, simultaneous horizontal encoder access,
active/reconnecting output protection, failed-start blocking, stale-profile binding
protection, route authorization/capabilities and service-neutral UI controls.
Windows compilation, packaging and browser checks run in the release workflow.
Real OBS broadcast and reconnect acceptance remain required before stable 1.0.0.


RC5 Windows validation passed:
- Source: `7145b007fb401a60025c0d6dfbb375d04126585d`.
- Build: https://github.com/Dakotalamb/ForgeCast/actions/runs/39088300418
- Installer: `FDGCast-1.0.0-rc.5-win-x64-setup.exe` (22,706,615 bytes).
- SHA-256: `ef686e6175c14bba9bb116c4861683c72e2312a1fb3f4f2bdb1b4dcbee7eea99`.
- Native geometry/routing tests, OBS 32.2.2 compilation, Python regression,
  four browser suites, packaging and installed-module startup/location checks passed.
- This is a release candidate, not stable 1.0.0. Real broadcasts and GPU/resource
  benchmarks remain unverified. No stable update feed or Hub deployment changed.
