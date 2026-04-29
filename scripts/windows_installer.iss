#define MyAppName "Thesis Monitor"
#define MyAppPublisher "Thesis Project"
#define MyAppURL "https://github.com/kaizen-2004/capstone-repository"
#define MyAppExeName "run_thesis_monitor.bat"
#define MyAppVersion "1.0.0"

#ifndef SourceRoot
  #define SourceRoot ".."
#endif

[Setup]
AppId={{6F5A98B8-2E18-4A63-9C41-A845EE26D91A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\ThesisMonitor
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#SourceRoot}\installer\dist
OutputBaseFilename=ThesisMonitorSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\backend\dist\backend\backend.exe
ChangesEnvironment=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceRoot}\installer\staging\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\backend\dist\backend\backend.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\backend\dist\backend\backend.exe"

[Run]
Filename: "{app}\prereqs\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ Runtime..."; Flags: waituntilterminated skipifdoesntexist; Check: NeedsVCRedist
Filename: "{app}\prereqs\Tailscale-setup.exe"; Parameters: "/S"; StatusMsg: "Installing Tailscale..."; Flags: waituntilterminated skipifdoesntexist; Check: NeedsTailscale
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function NeedsVCRedist: Boolean;
begin
  Result :=
    FileExists(ExpandConstant('{app}\prereqs\vc_redist.x64.exe')) and
    not RegKeyExists(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') and
    not RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64');
end;

function NeedsTailscale: Boolean;
begin
  Result :=
    FileExists(ExpandConstant('{app}\prereqs\Tailscale-setup.exe')) and
    not FileExists(ExpandConstant('{pf}\Tailscale\tailscale-ipn.exe')) and
    not FileExists(ExpandConstant('{pf64}\Tailscale\tailscale-ipn.exe'));
end;
