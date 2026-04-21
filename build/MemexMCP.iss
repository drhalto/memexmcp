; MemexMCP - Windows installer.
;
; Build:  iscc build\MemexMCP.iss   (after running build-reuse-venv.ps1)
;
; This installer is intentionally minimal: it copies three frozen exes,
; creates Start Menu / desktop shortcuts, and registers an uninstaller.
; All actual setup (tier choice, Gemini key, Ollama install, model pull)
; is handled by the in-app first-launch wizard inside Memex.exe.

#define AppName        "Memex"
#define AppVersion     "0.1.0"
#define AppPublisher   "Dustin"
#define AppExeGui      "Memex.exe"
#define AppExeMcp      "MemexMCP-Server.exe"
#define AppExeCli      "memex-cli.exe"

[Setup]
AppId={{8F2E4A7C-9B3D-4A5E-8F6B-MEMEXMCP00001}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\MemexMCP
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=MemexMCP-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeGui}
SetupIconFile=..\assets\icon.ico
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\{#AppExeGui}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\{#AppExeMcp}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\{#AppExeCli}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeGui}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}";     Filename: "{app}\{#AppExeGui}"; Tasks: desktopicon

[Run]
; Launch Memex after install (user-optional). On first launch, the
; in-app setup wizard takes over: tier choice, Gemini key, Ollama install,
; model pull, MCP config snippet.
Filename: "{app}\{#AppExeGui}"; Description: "Launch Memex"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Leave the user's data (collections/, index.db) alone unless they delete
; %LOCALAPPDATA%\MemexMCP themselves. Just remove the config so a re-install
; re-prompts the wizard.
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\mcp-config.json"
