# Native OBS module: build and live-test gate

A previous Windows build compiled the native module and installer against OBS
32.2.2 in GitHub Actions. The renamed FDGCast build needs its own CI run.
Live installation and streaming tests have not been completed.
Do not claim this source is production-ready. Runtime and ABI compatibility must
be checked against the exact OBS version you use.

## Windows prerequisites

- Visual Studio 2022 C++ desktop tools (x64).
- CMake 3.24+.
- OBS development artifacts that export `OBS::libobs` and `OBS::obs-frontend-api`.
- Matching Qt6 Core, Widgets and Network development libraries.

Use the official OBS build guide to obtain matching artifacts:
https://github.com/obsproject/obs-studio/wiki/build-instructions-for-windows
The OBS plugin template is another supported starting point for SDK provisioning:
https://github.com/obsproject/obs-plugintemplate

From this project's root, with CMAKE_PREFIX_PATH set to your installed OBS and
matching Qt SDK prefixes (replace the paths below):

```powershell
cmake -S native -B build -A x64 '-DCMAKE_PREFIX_PATH=C:/dev/obs-install;C:/dev/qt'
cmake --build build --config Release
cmake --install build --config Release --prefix stage
```

The expected output is `stage/forgecast/bin/64bit/forgecast.dll`. If CMake cannot find
libobs or obs-frontend-api, the SDK export paths are not configured; installing
ordinary OBS alone does not provide these development artifacts.

Close OBS. On Windows the installer places the staged DLL at
`C:\ProgramData\obs-studio\plugins\forgecast\bin\64bit\forgecast.dll`.
For isolated testing, copy the staged DLL into a separate test OBS installation's
matching plugin directory. Do not replace any standard OBS DLLs or bundle an
incompatible Qt runtime. Start the test OBS, verify Docks → FDGCast Control,
then start the local companion. The bridge token's default location is fixed;
do not use `--data-dir` with the native module without modifying its path.

## Live test matrix (not completed here)

1. Start and exit OBS repeatedly; verify clean dock/module teardown.
2. Without the companion, confirm OBS still opens and the native stop button works.
3. Connect the companion; confirm the native indicator turns connected.
4. In a private/unlisted test, start main H.264/AAC stream.
5. Add one secondary destination and start it, verifying actual video/audio arrival.
6. Test invalid keys, unreachable server and delayed connection. Confirm no endless
   busy state; start failures must never be shown as confirmed live.
7. Verify secondary stop, main-stop cascade and OBS shutdown.
8. Test reconnect after a controlled network interruption; inspect frame counters.
9. Stop/start the same destination repeatedly and check memory/encoder references.
10. Close/restart companion while outputs run; native emergency stop must still work.
11. Test settings edits while active, queue expiry, repeated button presses, and
    reject AV1/HEVC or incompatible Enhanced Broadcasting setups.
12. Verify stream keys never appear in UI reports; inspect OBS logs before sharing.
13. Monitor CPU/GPU/memory/network while gaming. No performance benefit is assumed.

Native commands are deliberately at-most-once and expire after 10 seconds. If an
HTTP response is lost, the command can be lost rather than replayed. Inspect the
output state before pressing Start again. There is no unattended start automation.

## Packaging a Windows test installer

`packaging/build-windows.ps1` compiles the DLL against supplied OBS SDK and Qt6
development prefixes, freezes the companion with PyInstaller, then invokes Inno
Setup 6 to create `release/FDGCast-0.4.0-preview-win-x64-setup.exe`. The OBS
development artifacts must export `OBS::libobs` and `OBS::obs-frontend-api`; a
normal OBS desktop installation alone is insufficient. Example, in PowerShell:

```powershell
.\packaging\build-windows.ps1 -ObsSdkPrefix 'C:\dev\obs-sdk' -QtPrefix 'C:\Qt\6.x\msvc2022_64'
```

This script has not run on Windows here. A generated installer still needs
installation, uninstall, OBS load, chat, streaming and security checks on an
isolated Windows OBS setup before public distribution. Do not advertise OBS
version compatibility based only on CMake success.
