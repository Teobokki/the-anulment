#define MyVer "1.0.0"
[Setup]
AppId={{B4D27E19-6A3C-4F85-9E1D-52A7C0F3D861}
AppName=THE ANULMENT
AppVersion={#MyVer}
AppVerName=THE ANULMENT {#MyVer}
AppPublisher=EX Inc./HYPERION DIGITAL
AppPublisherURL=https://github.com/Teobokki/the-anulment
AppCopyright=©2026 EX Inc./HYPERION DIGITAL ©2026
VersionInfoVersion={#MyVer}
VersionInfoCompany=EX Inc./HYPERION DIGITAL
VersionInfoCopyright=©2026 EX Inc./HYPERION DIGITAL ©2026
VersionInfoProductName=THE ANULMENT
VersionInfoDescription=THE ANULMENT Setup
DefaultDirName={localappdata}\Programs\THE ANULMENT
DefaultGroupName=THE ANULMENT
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=THE-ANULMENT-Setup-{#MyVer}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\THE ANULMENT.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\THE ANULMENT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\THE ANULMENT"; Filename: "{app}\THE ANULMENT.exe"
Name: "{group}\Uninstall THE ANULMENT"; Filename: "{uninstallexe}"
Name: "{userdesktop}\THE ANULMENT"; Filename: "{app}\THE ANULMENT.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\THE ANULMENT.exe"; Description: "Launch THE ANULMENT now"; Flags: nowait postinstall skipifsilent
