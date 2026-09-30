; Build only after compiling the matching OBS x64 DLL and freezing the companion.
; Installs only FDGCast files and leaves OBS itself untouched.
[Setup]
AppId={{C47C9B69-A4E0-4F8B-8D90-6D4CCF944210}
AppName=FDGCast
AppVersion=0.4.0 Preview
AppPublisher=Forged Destiny Gaming
AppPublisherURL=https://forgeddestinygaming.com/
SetupIconFile={#SourcePath}FDGCast.ico
UninstallDisplayIcon={app}\FDGCast.exe
DefaultDirName={autopf}\Forged Destiny Gaming\FDGCast
DefaultGroupName=FDGCast
OutputDir={#SourcePath}..\release
OutputBaseFilename=FDGCast-0.4.0-preview-win-x64-setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=FDGCast (OBS module and desktop companion)
WizardStyle=modern

[Files]
Source: "{#SourcePath}..\dist\FDGCast\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourcePath}..\stage\forgecast\bin\64bit\forgecast.dll"; DestDir: "{commonappdata}\obs-studio\plugins\forgecast\bin\64bit"; Flags: ignoreversion
Source: "{#SourcePath}en-US.ini"; DestDir: "{commonappdata}\obs-studio\plugins\forgecast\data\locale"; Flags: ignoreversion
Source: "{#SourcePath}FDGCast.ico"; DestDir: "{commonappdata}\obs-studio\plugins\forgecast\data"; Flags: ignoreversion
Source: "{#SourcePath}..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\FDGCast"; Filename: "{app}\FDGCast.exe"; IconFilename: "{app}\FDGCast.exe"; AppUserModelID: "ForgedDestinyGaming.FDGCast"
Name: "{autodesktop}\FDGCast"; Filename: "{app}\FDGCast.exe"; IconFilename: "{app}\FDGCast.exe"; AppUserModelID: "ForgedDestinyGaming.FDGCast"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\FDGCast.exe"; Description: "Start FDGCast companion"; Flags: postinstall nowait skipifsilent unchecked

[UninstallDelete]
; User settings and DPAPI secrets in LOCALAPPDATA are intentionally preserved on uninstall.

[InstallDelete]
; Replacing an earlier preview keeps its OBS module ID and private settings, but removes old launchers.
Type: files; Name: "{app}\ForgeCast.exe"
Type: files; Name: "{group}\ForgeCast.lnk"
Type: files; Name: "{autodesktop}\ForgeCast.lnk"
