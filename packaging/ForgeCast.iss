; Build only after compiling the matching OBS x64 DLL and freezing the companion.
; Installs only ForgeCast files and leaves OBS itself untouched.
[Setup]
AppId={{C47C9B69-A4E0-4F8B-8D90-6D4CCF944210}
AppName=ForgeCast
AppVersion=0.3.3 Preview
AppPublisher=Forged Destiny Gaming
AppPublisherURL=https://forgeddestinygaming.com/
DefaultDirName={autopf}\Forged Destiny Gaming\ForgeCast
DefaultGroupName=ForgeCast
OutputDir={#SourcePath}..\release
OutputBaseFilename=ForgeCast-0.3.3-preview-win-x64-setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=ForgeCast (OBS module and desktop companion)
WizardStyle=modern

[Files]
Source: "{#SourcePath}..\dist\ForgeCast\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourcePath}..\stage\forgecast\bin\64bit\forgecast.dll"; DestDir: "{commonappdata}\obs-studio\plugins\forgecast\bin\64bit"; Flags: ignoreversion
Source: "{#SourcePath}en-US.ini"; DestDir: "{commonappdata}\obs-studio\plugins\forgecast\data\locale"; Flags: ignoreversion
Source: "{#SourcePath}..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ForgeCast"; Filename: "{app}\ForgeCast.exe"
Name: "{autodesktop}\ForgeCast"; Filename: "{app}\ForgeCast.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\ForgeCast.exe"; Description: "Start ForgeCast companion"; Flags: postinstall nowait skipifsilent unchecked

[UninstallDelete]
; User settings and DPAPI secrets in LOCALAPPDATA are intentionally preserved on uninstall.
