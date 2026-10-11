; IBKR Portfolio Advisor - one-file installer (Inno Setup 6)
; Built by build.bat or the GitHub Actions workflow -> dist\Installer-IBKR-Advisor.exe
; Per-user install: no admin rights. Vedware runs it silently for updates (/VERYSILENT).

#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{78C65899-FA9D-4D3A-BDE6-ABA2C64C97C4}
AppName=IBKR Advisor
AppVersion={#AppVersion}
AppVerName=IBKR Advisor {#AppVersion}
AppPublisher=Sébastien Védrine
AppPublisherURL=https://github.com/sebastien-vedrine/ibkr-advisor
AppSupportURL=https://github.com/sebastien-vedrine/ibkr-advisor/issues
AppUpdatesURL=https://github.com/sebastien-vedrine/ibkr-advisor/releases
DefaultDirName={localappdata}\Programs\IBKR Advisor
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename=Installer-IBKR-Advisor
UninstallDisplayIcon={app}\IBKR-Advisor.exe
UninstallDisplayName=IBKR Advisor
VersionInfoVersion={#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=auto
CloseApplications=force
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[CustomMessages]
en.DesktopIcon=Put an IBKR Advisor icon on the desktop
fr.DesktopIcon=Mettre une icône IBKR Advisor sur le Bureau
en.OpenNow=Open IBKR Advisor now
fr.OpenNow=Ouvrir IBKR Advisor maintenant

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"

[InstallDelete]
; clean update: remove the previous version's runtime files
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\IBKR-Advisor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\IBKR Advisor"; Filename: "{app}\IBKR-Advisor.exe"
Name: "{userdesktop}\IBKR Advisor"; Filename: "{app}\IBKR-Advisor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\IBKR-Advisor.exe"; Description: "{cm:OpenNow}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM IBKR-Advisor.exe /F"; Flags: runhidden; RunOnceId: "StopApp"
