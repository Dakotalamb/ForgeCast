# FDGCast Windows installer status

## Prepared in source

- FDG orange (`#ff531f`), dark charcoal and the Hub's existing F shield icon
  across the companion dock. The native OBS dock uses the same palette.
- OBS native module staged to the directory layout supported by OBS on Windows.
- Windows build script freezes the Python companion and compiles the OBS module
  against matching OBS/Qt development artifacts.
- Inno Setup recipe packages the companion, native DLL and documentation into
  one installation executable, with an uninstall entry.

## Windows preview build

The earlier ForgeCast preview compiled against OBS 32.2.2. The FDGCast 0.4.0
preview needs its own Windows Actions run before an installer can be linked.
The resulting build still needs to be tested in OBS on a creator PC.

## What is still required before public distribution

1. Install the generated EXE on a clean Windows OBS test machine. Check that
   OBS opens, that Docks → FDGCast Control appears, and that a reinstall and
   uninstall do not remove the user's saved OBS settings or FDGCast secrets.
2. Test Twitch Shared Chat with multiple broadcasters; YouTube and Kick live
   events; start/stop/reconnect of secondary RTMP outputs; and Stream Doctor
   while gaming. Verify OBS logs and installer antivirus/SmartScreen behavior.
3. Check each OBS release claimed as compatible. A DLL built against one OBS
   development kit is not proof of compatibility with the previous versions.
4. Prepare publication terms and source distribution for the native module,
   because it links to OBS. Finish a release review before offering the
   installer to other creators.

The Windows installer is **compiled but has not been live tested in OBS**.
See `docs/NATIVE_BUILD.md` for local build guidance.

The 0.3.0 preview adds native OBS Chat, Stream Doctor and Multistream docks and
changes the companion to a desktop window. Its Windows build passed native
compilation, desktop startup and installation-path checks. OBS runtime and
live-streaming tests on a creator PC remain. The 0.2.0 artifact lacks these docks.

The 0.4.0 preview places Stream Doctor beside Sources, FDGCast Events in the
Event List area, Chat beside Events, and Multistream beside Outputs on first
launch; subsequent OBS rearrangements
are preserved. The Control panel can bring the desktop app forward and reset
the FDGCast dock layout. The companion uses Hub pairing for account setup.
