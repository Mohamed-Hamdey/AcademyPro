; ============================================================================
;  AcademyPro — Inno Setup installer script
;
;  Wraps the PyInstaller-built AcademyPro.exe into a full Windows
;  installer with Start Menu entry, desktop icon, and uninstaller.
;
;  Build:
;    1. Ensure dist\AcademyPro\AcademyPro.exe exists (run PyInstaller first)
;    2. Open this file in Inno Setup Compiler
;    3. Press F9 (or Build > Compile)
;    4. The setup executable appears at:  dist_installer\AcademyPro_Setup_v4.0.0.exe
; ============================================================================

#define MyAppName "AcademyPro"
#define MyAppNameAr "اكاديمي برو"
#define MyAppVersion "4.0.0"
#define MyAppPublisher "AcademyPro"
#define MyAppExeName "AcademyPro.exe"
#define MyAppDataDir "AcademySystem"
; ^^^ CRITICAL: DO NOT CHANGE THIS. It matches the folder name used by
;     paths.py for user data (%LOCALAPPDATA%\AcademySystem). Changing it
;     would orphan every existing user's database on update.

[Setup]
; ---- Identity ----
AppId={{8F4C8A2E-1B7D-4C2A-9E5F-3A7B8C9D0E1F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
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
OutputBaseFilename=AcademyPro_Setup_v{#MyAppVersion}
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
Source: "dist\AcademyPro\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

Source: "README.md";        DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "README_DEPLOY.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{group}\Read me";                Filename: "{app}\README.md"

Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]

[Code]
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
        MB_YESNO or MB_DEFBUTTON2
      );

      if Response = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;