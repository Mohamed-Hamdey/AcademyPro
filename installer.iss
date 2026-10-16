; ============================================================================
;  Academy System — Inno Setup installer script
;
;  Wraps the PyInstaller-built AcademySystem.exe into a full Windows
;  installer with Start Menu entry, desktop icon, and uninstaller.
;
;  Build:
;    1. Ensure dist\AcademySystem.exe exists (run build.bat first)
;    2. Open this file in Inno Setup Compiler
;    3. Press F9 (or Build > Compile)
;    4. The setup executable appears at:  dist_installer\AcademySystem_Setup.exe
; ============================================================================

#define MyAppName "Academy System"
#define MyAppNameAr "نظام العضوية"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AL-Abtal Kung Fu Academy"
#define MyAppExeName "AcademySystem.exe"
#define MyAppDataDir "AcademySystem"

[Setup]
; ---- Identity ----
AppId={{8F4C8A2E-1B7D-4C2A-9E5F-3A7B8C9D0E1F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
; ---- License agreement ----
LicenseFile=installer\EULA.txt

; ---- Uninstall ----
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; ---- Privileges ----
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
; ---- Install location ----
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
AllowNoIcons=yes

; ---- Output ----
OutputDir=dist_installer
OutputBaseFilename=AcademySystem_Setup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; ---- Icon for the installer itself ----
SetupIconFile=assets\logo\logo.ico

; ---- Visuals ----
WizardStyle=modern
DisableWelcomePage=no
DisableDirPage=no
DisableReadyPage=no





[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.CreateDesktopIcon=Create a &desktop shortcut
english.AdditionalIcons=Additional shortcuts:
english.LaunchApp=Launch {#MyAppName} now
english.DeleteUserDataPrompt=Do you also want to delete your player data?%n%nThis includes all players, subscriptions, and attendance records.%n%nChoose "No" if you plan to reinstall {#MyAppName} later and want to keep your data. Choose "Yes" to completely remove everything.
english.DeleteUserDataTitle=Delete user data?
arabic.CreateDesktopIcon=إنشاء &اختصار على سطح المكتب
arabic.AdditionalIcons=اختصارات إضافية:
arabic.LaunchApp=تشغيل {#MyAppName} الآن
arabic.DeleteUserDataPrompt=هل تريد أيضًا حذف بيانات اللاعبين؟%n%nيشمل ذلك جميع اللاعبين والاشتراكات وسجلات الحضور.%n%nاختر "لا" إذا كنت تنوي إعادة تثبيت {#MyAppName} لاحقًا وتريد الاحتفاظ ببياناتك. اختر "نعم" لحذف كل شيء نهائيًا.
arabic.DeleteUserDataTitle=حذف بيانات المستخدم؟

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "startmenuicon"; Description: "Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; The main executable
Source: "dist\AcademySystem\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; Documentation
Source: "README.md";        DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "README_DEPLOY.md"; DestDir: "{app}"; Flags: ignoreversion

; Optional: uncomment if you want to ship a license file
; Source: "installer\LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{group}\Read me";                Filename: "{app}\README.md"

; Desktop (optional task)
Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Offer to launch the app after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Do NOT delete user data automatically — we ask via code below.

[Code]
// ---------------------------------------------------------------------------
// On uninstall: ask the user whether to keep or delete their data folder.
// ---------------------------------------------------------------------------
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  Response: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\{#MyAppDataDir}');

    if DirExists(DataDir) then
    begin
      Response := MsgBox(
        ExpandConstant('{cm:DeleteUserDataPrompt}'),
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2  // default = No (keep data)
      );

      if Response = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;