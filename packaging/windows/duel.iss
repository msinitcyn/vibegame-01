; Установщик «Дуэли шариков» для Windows (Inno Setup 6).
; Собирается tools\build.py после PyInstaller:  iscc /DAppVersion=0.2.0 packaging\windows\duel.iss
; Ставит для текущего пользователя (без администратора), ярлыки в «Пуск» и на рабочем столе.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6A2D5096-AB5C-4109-9563-74014CD8F39B}
AppName=Дуэль шариков
AppVersion={#AppVersion}
AppPublisher=fast-game
DefaultDirName={autopf}\Duel
DefaultGroupName=Дуэль шариков
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=duel-setup
SetupIconFile=..\..\build\icon.ico
UninstallDisplayIcon={app}\duel.exe
UninstallDisplayName=Дуэль шариков
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "fi"; MessagesFile: "compiler:Languages\Finnish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\duel-windows.exe"; DestDir: "{app}"; DestName: "duel.exe"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Дуэль шариков"; Filename: "{app}\duel.exe"
Name: "{autodesktop}\Дуэль шариков"; Filename: "{app}\duel.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\duel.exe"; Description: "{cm:LaunchProgram,Дуэль шариков}"; Flags: nowait postinstall skipifsilent
