# Vertical Studio

Open the dedicated Vertical Studio tab in Companion. Connect OBS WebSocket in
Connections, then refresh OBS sources. No extra OBS docks, camera captures or
Browser Sources are created.

1. Choose the OBS scene to arrange, or leave Follow the live OBS scene enabled.
2. Choose Full screen, Whole picture, Camera top, Camera bottom, Camera corner,
   Two cameras or Freeform. Presets are starting points, not face tracking.
3. Select a picture layer and choose its existing OBS game/camera source. Full
   OBS scene reuses the scene picture. Empty sources remain empty until assigned.
4. Drag/resize on the vertical preview or enter pixel positions/sizes. Adjust
   fill/fit, zoom, crop position, mirroring, visibility, layer order and background.
5. Save scene layout. Save applies to live vertical outputs; unsaved edits only
   change the preview. Scene-specific layouts fall back to the saved default,
   then to a full-scene center crop. Unsaved edits pause editor scene following.
6. Select a saved destination and click Use Vertical Studio. Stop that
   destination before changing its picture format. Start it in Destinations or
   use Start All, which starts the main OBS stream and checked destinations.

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
