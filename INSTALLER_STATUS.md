# ForgeCast Windows installer status

## Prepared in source

- FDG orange (`#ff531f`), dark charcoal and the Hub's existing F shield icon
  across the companion dock. The native OBS dock uses the same palette.
- OBS native module staged to the directory layout supported by OBS on Windows.
- Windows build script freezes the Python companion and compiles the OBS module
  against matching OBS/Qt development artifacts.
- Inno Setup recipe packages the companion, native DLL and documentation into
  one installation executable, with an uninstall entry.

## Windows preview build

The GitHub Actions Windows runner compiled the native module against OBS
32.2.2, froze the companion, and produced an Inno Setup installer on
2026-09-27. The successful build is linked from the repository's Actions tab.
It has not yet been installed or exercised inside OBS on a creator PC.

## What is still required before public distribution

1. Install the generated EXE on a clean Windows OBS test machine. Check that
   OBS opens, that Docks → ForgeCast Control appears, and that a reinstall and
   uninstall do not remove the user's saved OBS settings or ForgeCast secrets.
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
