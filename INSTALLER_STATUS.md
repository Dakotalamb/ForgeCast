# ForgeCast Windows installer status

## Prepared in source

- FDG orange (`#ff531f`), dark charcoal and the Hub's existing F shield icon
  across the companion dock. The native OBS dock uses the same palette.
- OBS native module staged to the directory layout supported by OBS on Windows.
- Windows build script freezes the Python companion and compiles the OBS module
  against matching OBS/Qt development artifacts.
- Inno Setup recipe packages the companion, native DLL and documentation into
  one installation executable, with an uninstall entry.

## What is still required before users can install it

1. Build on Windows with matching OBS 64-bit development artifacts, Qt6,
   Visual Studio C++ tools, Python, CMake and Inno Setup 6. The build script
   intentionally stops when any prerequisite or output is missing.
2. Install the generated EXE on a clean Windows OBS test machine. Check that
   OBS opens, that Docks → ForgeCast Control appears, and that a reinstall and
   uninstall do not remove the user's saved OBS settings or ForgeCast secrets.
3. Test Twitch Shared Chat with multiple broadcasters; YouTube and Kick live
   events; start/stop/reconnect of secondary RTMP outputs; and Stream Doctor
   while gaming. Verify OBS logs and installer antivirus/SmartScreen behavior.
4. Check each OBS release claimed as compatible. A DLL built against one OBS
   development kit is not proof of compatibility with the previous versions.
5. Prepare publication terms and source distribution for the native module,
   because it links to OBS. Finish a release review before offering the
   installer to other creators.

There is **no compiled or tested installer** in this archive. Building and
testing it on Windows is the remaining release gate; this file does not imply
those steps passed. See `docs/NATIVE_BUILD.md` for the build command.
