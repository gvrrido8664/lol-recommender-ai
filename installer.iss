; Inno Setup script for NEXUS - LoL Recommender
; Genera: build_onedir\NEXUS_Setup_{version}.exe
; Requiere Inno Setup 6+: https://jrsoftware.org/isdl.php
;
; Uso: ISCC.exe installer.iss   (o build_exe.ps1 -Installer)

#define MyAppName "NEXUS"
#define MyAppVersion GetFileVersion("build_onedir\NEXUS\NEXUS.exe")
#if MyAppVersion == ""
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "NEXUS"
#define MyAppURL "https://github.com/gvrrido8664/lol-recommender-ai"
#define MyAppExeName "NEXUS.exe"

[Setup]
AppId={{B4F8A9D2-7E3C-4C5A-A1B6-9D8E7F3C2A5B}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; El usuario elige donde instalar (default: %LOCALAPPDATA%\NEXUS)
DefaultDirName={localappdata}\{#MyAppName}
DisableProgramGroupPage=yes
OutputDir=build_onedir
OutputBaseFilename=NEXUS_Setup_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Instala sin pedir admin (el usuario puede cambiar a Program Files si quiere)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Desinstalador en Panel de Control
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Files]
Source: "build_onedir\NEXUS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTA: los secretos (API_KEY, DATABASE_URL) van cifrados en secretos.bin DENTRO
; del bundle de la app (build_onedir\NEXUS\*). NO se shippea config.json en claro.

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
