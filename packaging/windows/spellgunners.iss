; Установщик Spellgunners для Windows (Inno Setup 6).
; Собирается tools\build.py после PyInstaller:  iscc /DAppVersion=0.2.0 packaging\windows\spellgunners.iss
; Ставит для текущего пользователя (без администратора), ярлыки в «Пуск» и на рабочем столе.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6A2D5096-AB5C-4109-9563-74014CD8F39B}
AppName=Spellgunners
AppVersion={#AppVersion}
AppPublisher=Spellgunners
DefaultDirName={autopf}\Spellgunners
DefaultGroupName=Spellgunners
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=spellgunners-setup
SetupIconFile=..\..\build\icon.ico
UninstallDisplayIcon={app}\spellgunners.exe
UninstallDisplayName=Spellgunners
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
Source: "..\..\dist\spellgunners-windows.exe"; DestDir: "{app}"; DestName: "spellgunners.exe"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Spellgunners"; Filename: "{app}\spellgunners.exe"
Name: "{autodesktop}\Spellgunners"; Filename: "{app}\spellgunners.exe"; Tasks: desktopicon

[Code]
// Автообновление запускает установщик и сразу выходит из игры — ждём, пока игра закроется
// (мьютекс берёт duel/single.py), иначе spellgunners.exe занят, замена не удаётся и всё откатывается.
function InitializeSetup(): Boolean;
var
  i: Integer;
begin
  i := 0;
  while CheckForMutexes('SpellgunnersRunning') and (i < 100) do
  begin
    Sleep(200);
    i := i + 1;
  end;
  if i > 0 then
    Sleep(2000)    // собранная игра (onefile) ещё секунду-другую убирает за собой и держит файл
  else if WizardSilent then
    Sleep(4000);   // обновление из версии до 0.7.2: мьютекса там нет — просто даём игре закрыться
  if CheckForMutexes('SpellgunnersRunning') and not WizardSilent then
    MsgBox('Spellgunners ещё открыт — закройте игру, и установка продолжится.', mbInformation, MB_OK);
  Result := True;
end;

[Run]
Filename: "{app}\spellgunners.exe"; Description: "{cm:LaunchProgram,Spellgunners}"; Flags: nowait postinstall skipifsilent
; автообновление ставит тихо (/SILENT) — тогда игру запускаем сами
Filename: "{app}\spellgunners.exe"; Flags: nowait; Check: WizardSilent
