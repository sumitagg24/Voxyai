; Voxylis Windows installer (Inno Setup 6)
;
; PyInstaller produces a folder of files, which is not something a consumer
; should be asked to unzip. This script wraps that folder in a real installer
; with a Start Menu entry, an uninstaller, an upgrade path and (optionally) a
; desktop shortcut.
;
; Build:
;   1. pyinstaller voxylis.spec            -> dist\Voxylis\
;   2. iscc /DAppVersion=3.0.0 installer\voxylis.iss
;   -> installer\output\Voxylis-Setup-3.0.0.exe
;
; The version is passed in from config/version.py by build_windows.bat so the
; installer, the EXE metadata and /api/health can never disagree.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName        "Voxylis"
#define AppPublisher   "Voxylis"
#define AppURL         "https://github.com/sumitagg24/Voxyai"
#define AppExeName     "Voxylis.exe"
#define SourceDir      "..\dist\Voxylis"

[Setup]
AppId={{8E6B1F42-6C7A-4E2C-9E0E-2F4A6C1B7D31}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} voice dictation setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

; Per-user by default: no UAC prompt, and everything mutable already lives in
; %LOCALAPPDATA%. Set /DPrivilegesRequired=admin for a machine-wide install.
#ifndef PrivilegesRequired
  #define PrivilegesRequired "lowest"
#endif
PrivilegesRequired={#PrivilegesRequired}
PrivilegesRequiredOverridesAllowed=dialog

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
AllowNoIcons=yes

OutputDir=output
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
SetupIconFile=..\packaging\voxylis.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}

Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no
; Uninstall must not delete the user's data outside {app}.
Uninstallable=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startup"; Description: "Start {#AppName} when I sign in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; Startup entry is written per-user so the task works without elevation.
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Nothing to stop: the app closes itself before the installer replaces files.

[UninstallDelete]
; Only build output that we created. User data lives in %LOCALAPPDATA%\Voxylis
; and is deliberately left alone; the app's Privacy page can delete it.
Type: filesandordirs; Name: "{app}\_internal"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // Offer to remove local user data on explicit uninstall, but never silently.
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('Also delete your local Voxylis data (settings, history and logs in %LOCALAPPDATA%\Voxylis)?',
              mbConfirmation, MB_YESNO) = IDYES then
      DelTree(ExpandConstant('{localappdata}\Voxylis'), True, True, True);
  end;
end;
