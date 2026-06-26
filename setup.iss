; V-Agent v0.7 Setup Script
; For Inno Setup 6.x
; Download from: https://jrsoftware.org/isinfo.php
;
; To create installer:
;   1. Install Inno Setup
;   2. File → Open → setup.iss
;   3. Build → Compile

[Setup]
AppName=V-Agent
AppVersion=0.7
AppPublisher=V-Agent Contributors
AppPublisherURL=https://github.com
AppSupportURL=https://github.com
AppUpdatesURL=https://github.com
DefaultDirName={localappdata}\V-Agent
DefaultGroupName=V-Agent
OutputDir=.
OutputBaseFilename=V-Agent-Setup
SetupIconFile=assets\vagent.ico
UninstallDisplayIcon={app}\V-Agent.exe
Compression=lz4
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
AllowNoIcons=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenu";  Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checked
Name: "ollama";     Description: "Open Ollama website after installation"; GroupDescription: "Post-Install"; Flags: unchecked

[Files]
Source: "dist\V-Agent.exe";            DestDir: "{app}";     Flags: ignoreversion
Source: "dist\V-Agent-Automator.exe";  DestDir: "{app}";     Flags: ignoreversion
Source: "dist\automator.py";           DestDir: "{app}";     Flags: ignoreversion
Source: "dist\config.json";            DestDir: "{app}";     Flags: ignoreversion onlyifdoesntexist
Source: "dist\README.md";              DestDir: "{app}";     Flags: ignoreversion
Source: "dist\LICENSE";                DestDir: "{app}";     Flags: ignoreversion
Source: "dist\start.bat";              DestDir: "{app}";     Flags: ignoreversion
Source: "dist\Input\*";                DestDir: "{app}\Input"; Flags: ignoreversion
Source: "dist\Output\*";               DestDir: "{app}\Output"; Flags: ignoreversion
Source: "dist\bin\*";                  DestDir: "{app}\bin"; Flags: ignoreversion
Source: "assets\*";                    DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{group}\V-Agent";                      Filename: "{app}\V-Agent.exe"; WorkingDir: "{app}"
Name: "{group}\V-Agent Automator";            Filename: "{app}\V-Agent-Automator.exe"; WorkingDir: "{app}"
Name: "{group}\Edit Configuration";           Filename: "{app}\config.json"; WorkingDir: "{app}"
Name: "{group}\README";                       Filename: "{app}\README.md"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,V-Agent}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\V-Agent";              Filename: "{app}\V-Agent.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\V-Agent.exe"; Description: "{cm:LaunchProgram,V-Agent}"; Flags: nowait postinstall skipifsilent
Filename: "https://ollama.com/download/windows"; Flags: shellexec; Tasks: ollama

[UninstallDelete]
Type: dirifempty; Name: "{app}\Input"
Type: dirifempty; Name: "{app}\Output"
Type: dirifempty; Name: "{app}\bin"
Type: dirifempty; Name: "{app}\assets"
Type: dirifempty; Name: "{app}"

[Messages]
WelcomeLabel1=Welcome to V-Agent Setup
WelcomeLabel2=This will install V-Agent v0.7, a local AI coding agent powered by Ollama.%n%nNo API keys. No telemetry. Your code never leaves your machine.
FinishedHeadingText=Setup Complete
FinishedLabelText=V-Agent has been installed successfully.%n%nNext: Run Ollama (https://ollama.com) and V-Agent will connect automatically.
ClickFinish=Click Finish to launch V-Agent.

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    MsgBox('V-Agent is ready!%n%nNext steps:%n' +
           '1. Download and run Ollama from https://ollama.com%n' +
           '2. In a terminal, run: ollama serve%n' +
           '3. Pull a model: ollama pull qwen2.5-coder:14b%n' +
           '4. V-Agent will connect automatically.',
           mbInformation, MB_OK);
  end;
end;
