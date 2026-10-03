# FDGCast 0.6.0 Preview release verification

Compiled source: `13304e460a7a8611204571eaedb2f8394acf5a5f`.

Windows build and checks: https://github.com/Dakotalamb/ForgeCast/actions/runs/37159725168

- Native OBS module compiled against OBS Studio 32.2.2.
- 145 Python regression tests passed on Windows and locally.
- Companion Chromium checks passed: Overview without duplicate chat, all five tabs, update banner/release notes/download target, platform server presets, masked saved setup fields, blocked demo live actions, no JavaScript errors and no mobile horizontal overflow.
- PyInstaller desktop-window, icon and single-instance checks passed.
- Inno Setup installer build and smoke installation passed.
- Downloaded artifact digest verified before extracting the installer.

Installer: `FDGCast-0.6.0-preview-win-x64-setup.exe` (13207635 bytes).

Installer SHA-256: `99a23ca479336a8e8b2f1931041090e89e6598914e0d583982d5fdbefceebfe1`.

Close OBS and Companion before installing over the previous release. Configuration and Windows-protected credentials are preserved. Existing 0.5.5 users need this initial upgrade manually; future notices become available after the Hub publishes the update feed described in UPDATES.md.

Live platform delivery, real OBS dock dragging/resizing and Windows notification/audio perception still need tests on the user's installation. Google OAuth verification and public Hub release/download deployment are external prerequisites. See POLISH_0.6.0.md and UPDATES.md.
