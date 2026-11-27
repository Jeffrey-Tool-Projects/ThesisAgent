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
; The list of program files an installation put in its folder.
#define Manifest "thesisagents-files.txt"

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
; RecordFile writes down every file installed, so the next version removes
; exactly those and nothing a user saved in the folder.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; AfterInstall: RecordFile

[UninstallDelete]
Type: files; Name: "{app}\{#Manifest}"

[Icons]
Name: "{group}\ThesisAgents"; Filename: "{app}\thesisagents.exe"
Name: "{group}\{cm:UninstallProgram,ThesisAgents}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\ThesisAgents"; Filename: "{app}\thesisagents.exe"; Tasks: desktopicon

[Registry]
; First the note that this installation put the folder on PATH, then the
; change itself: both ask NotOnPath, which the second entry makes false. The
; uninstaller takes the folder off PATH only with the note, so a PATH entry
; the user had made before stays.
Root: HKCU; Subkey: "Software\ThesisAgents\Installer"; ValueType: dword; ValueName: "AddedToPath"; ValueData: "1"; Tasks: addtopath; Check: NotOnPath; Flags: uninsdeletekey
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NotOnPath

[Run]
Filename: "{app}\thesisagents.exe"; Description: "{cm:LaunchProgram,ThesisAgents}"; Flags: nowait postinstall skipifsilent

[Code]
const
  EnvKey = 'Environment';
  InstallerKey = 'Software\ThesisAgents\Installer';

var
  InstalledFiles: TStringList;
  RemoveFromPath: Boolean;

{ Called after each file of [Files] is copied: note where it went. }
procedure RecordFile;
begin
  if InstalledFiles = nil then
    InstalledFiles := TStringList.Create;
  InstalledFiles.Add(ExpandConstant(CurrentFileName));
end;

{ Whether Path names a file inside the program folder. A list edited by hand
  must not point the cleanup anywhere else. }
function InProgramFolder(Path: string): Boolean;
var
  Folder: string;
begin
  Folder := Lowercase(AddBackslash(ExpandConstant('{app}')));
  Result := (Pos(Folder, Lowercase(Path)) = 1) and (Pos('..', Path) = 0)
    and (Length(Path) > Length(Folder));
end;

{ Remove the files the previous version installed, before the new ones are
  copied: a left-over module or DLL would be loaded by the new program. Only
  the files on its list go, so a library, PDF or export the user saved in the
  folder stays. An installation older than the list (v0.1.27) has none, and
  then nothing is removed. Folders are removed when they end up empty. }
procedure RemovePreviousFiles;
var
  Lines: TArrayOfString;
  Index: Integer;
  Folder, Directory: string;
begin
  if not LoadStringsFromFile(ExpandConstant('{app}\{#Manifest}'), Lines) then
    Exit;
  Folder := RemoveBackslash(ExpandConstant('{app}'));
  for Index := 0 to GetArrayLength(Lines) - 1 do
    if InProgramFolder(Lines[Index]) then
      DeleteFile(Lines[Index]);
  for Index := GetArrayLength(Lines) - 1 downto 0 do
    if InProgramFolder(Lines[Index]) then
    begin
      Directory := ExtractFileDir(Lines[Index]);
      while (CompareText(Directory, Folder) <> 0) and InProgramFolder(Directory) do
      begin
        if not RemoveDir(Directory) then
          Break;
        Directory := ExtractFileDir(Directory);
      end;
    end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    RemovePreviousFiles
  else if (CurStep = ssPostInstall) and (InstalledFiles <> nil) then
    InstalledFiles.SaveToFile(ExpandConstant('{app}\{#Manifest}'));
end;

function NotOnPath: Boolean;
var
  Paths: string;
begin
  if not RegQueryStringValue(HKCU, EnvKey, 'Path', Paths) then
    Paths := '';
  Result := Pos(';' + Lowercase(ExpandConstant('{app}')) + ';', ';' + Lowercase(Paths) + ';') = 0;
end;

{ Take the program folder off PATH again when it is uninstalled, but only
  when an installation put it there. The note is read before the uninstall
  starts, because the uninstall removes it with the rest of the registry
  entries. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Paths, Wrapped, Entry: string;
  At: Integer;
  Added: Cardinal;
begin
  if CurUninstallStep = usUninstall then
    RemoveFromPath := RegQueryDWordValue(HKCU, InstallerKey, 'AddedToPath', Added) and (Added = 1);
  if (CurUninstallStep <> usPostUninstall) or not RemoveFromPath then
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
