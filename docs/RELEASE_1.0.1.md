# FDGCast 1.0.1 — emergency main-stream recovery

Removes the main-output video override introduced in 1.0.0. OBS exclusively
controls its main stream's encoder, picture and startup again. Saved native
main-picture preferences are cleared on plugin startup. Vertical Studio remains
available on added FDGCast destinations; routing it to the OBS main output is
temporarily disabled and the interface explains this.

An unsafe 1.0.0 failure path could detach the main encoder when vertical setup
failed. That path is removed from production, and the retained routing helper
now rejects a missing picture/encoder without changing any existing video track.
This addresses an identified code defect; the reported zero-bitrate incident
still needs confirmation on the affected OBS installation.

## Immediate recovery / install

1. Stop streaming and close OBS and Companion.
2. Install 1.0.1, then reopen OBS. The main output uses the OBS service/settings.
3. Start the main stream in OBS and check for a nonzero bitrate and platform receipt.
4. Add other destinations afterward. Main-output Vertical Studio routing remains
   unavailable until it can be verified against a real OBS broadcast lifecycle.

If an installer is not available yet, close OBS and temporarily rename
C:\ProgramData\obs-studio\plugins\forgecast\bin\64bit\forgecast.dll
to forgecast.dll.disabled, then reopen OBS and stream normally. This bypasses
FDGCast's native plugin and disables its docks and secondary outputs.

The installer reinstalls forgecast.dll. If you used the temporary bypass,
the unused .disabled copy may be removed after installation.

Other 1.0.0 platform/Hub and resource limitations still apply.
