; Windows installer for the Nuitka build, compiled by release.yml with
;
;   ISCC.exe /DAppVersion=0.1.27 /DSourceDir=<thesisagents.dist> /DOutputDir=<dir> thesisagents.iss
;
; It installs for the current user only and asks for no administrator
; rights, so it works on a managed university computer. It is not signed
; (owner's decision), so SmartScreen warns the first time it is run.

#ifndef AppVersion
  #error Pass /DAppVersion=X.Y.Z
#endif
#ifndef SourceDir
  #error Pass /DSourceDir=path of thesisagents.dist
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
; Never change AppId: it is how an update finds the installed copy.
AppId={{6E0E4E0B-6C1B-4B0E-9C39-6F8D2C1C7A51}
AppName=ThesisAgents
AppVersion={#AppVersion}
AppPublisher=ThesisAgents
AppPublisherURL=https://github.com/Jeffrey-Tool-Projects/ThesisAgent
DefaultDirName={localappdata}\Programs\ThesisAgents
DefaultGroupName=ThesisAgents
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=thesisagents-setup-windows-x86_64
SetupIconFile=..\..\thesisagents\gui\icon.ico
UninstallDisplayIcon={app}\thesisagents.exe
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; The running app holds its files open. Setup asks to close it.
CloseApplications=yes
ChangesEnvironment=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "ko"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add thesisagents-cli to PATH"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ThesisAgents"; Filename: "{app}\thesisagents.exe"
Name: "{group}\{cm:UninstallProgram,ThesisAgents}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\ThesisAgents"; Filename: "{app}\thesisagents.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NotOnPath

[Run]
Filename: "{app}\thesisagents.exe"; Description: "{cm:LaunchProgram,ThesisAgents}"; Flags: nowait postinstall skipifsilent

[Code]
const
  EnvKey = 'Environment';

{ Whether the program folder is one this installer made and nothing else
  uses: it is called ThesisAgents, and it holds an installed copy. }
function IsOwnFolder: Boolean;
begin
  Result := (CompareText(ExtractFileName(RemoveBackslash(ExpandConstant('{app}'))), 'ThesisAgents') = 0)
    and FileExists(ExpandConstant('{app}\thesisagents-cli.exe'))
    and FileExists(ExpandConstant('{app}\unins000.exe'));
end;

{ Remove the previous version's files before the new ones are copied: a
  left-over module or DLL would be loaded by the new program. Settings, logs
  and libraries live elsewhere. The uninstaller's own files stay, and only a
  folder of ours is touched, because someone may have picked one that holds
  other files too. }
procedure CurStepChanged(CurStep: TSetupStep);
var
  Found: TFindRec;
  Folder: string;
begin
  if (CurStep <> ssInstall) or not IsOwnFolder then
    Exit;
  Folder := AddBackslash(ExpandConstant('{app}'));
  if FindFirst(Folder + '*', Found) then
  try
    repeat
      if (Found.Name <> '.') and (Found.Name <> '..')
        and (Pos('unins', Lowercase(Found.Name)) <> 1) then
        DelTree(Folder + Found.Name, True, True, True);
    until not FindNext(Found);
  finally
    FindClose(Found);
  end;
end;

function NotOnPath: Boolean;
var
  Paths: string;
begin
  if not RegQueryStringValue(HKCU, EnvKey, 'Path', Paths) then
    Paths := '';
  Result := Pos(';' + Lowercase(ExpandConstant('{app}')) + ';', ';' + Lowercase(Paths) + ';') = 0;
end;

{ Take the program folder off PATH again when it is uninstalled. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Paths, Wrapped, Entry: string;
  At: Integer;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  if not RegQueryStringValue(HKCU, EnvKey, 'Path', Paths) then
    Exit;
  Entry := ';' + ExpandConstant('{app}');
  Wrapped := ';' + Paths + ';';
  At := Pos(Lowercase(Entry) + ';', Lowercase(Wrapped));
  if At = 0 then
    Exit;
  Delete(Wrapped, At, Length(Entry));
  Paths := Copy(Wrapped, 2, Length(Wrapped) - 2);
  RegWriteExpandStringValue(HKCU, EnvKey, 'Path', Paths);
end;
