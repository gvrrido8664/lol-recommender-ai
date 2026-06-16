; Inno Setup script for NEXUS - LoL Recommender
; Generates: build_onedir\NEXUS_Setup_{version}.exe
; Requires Inno Setup 6+: https://jrsoftware.org/isdl.php
;
; Usage: ISCC.exe installer.iss   (or run build_exe.ps1 -Installer)

#define MyAppName "NEXUS"
#define MyAppVersion GetFileVersion("build_onedir\NEXUS\NEXUS.exe")
#if MyAppVersion == ""
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "NEXUS"
#define MyAppURL "https://github.com/gvrrido8664/lol-recommender-ai"
#define MyAppExeName "NEXUS.exe"

[Setup]
AppId={B4F8A9D2-7E3C-4C5A-A1B6-9D8E7F3C2A5B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=build_onedir
OutputBaseFilename=NEXUS_Setup_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardImageFile=build_onedir\NEXUS\_internal\PySide6\plugins\platforms\..\..\..\icon.ico
; No pedir permisos de admin: instala en %LOCALAPPDATA%
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Uninstall display info
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
; Signature (only if you have a real code signing cert)
; SignTool=mysigntool

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Files]
Source: "build_onedir\NEXUS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; El config.json NO va en el instalador (el usuario lo pone en %APPDATA%/LoLRecommender/)
; La app lo crea automaticamente si no existe al primer arranque.

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup: Boolean;
begin
  Result := True;
end;
