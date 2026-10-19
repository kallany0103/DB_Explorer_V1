#define MyAppName "Universal SQL Client"
#define MyAppVersion "1.44.2"
#define MyAppPublisher "Datafluent BD"
#define MyAppURL "https://www.datafluent.team"
#define MyAppExeName "Universal SQL Client.exe"

[Setup]
AppId={{6A6E3F74-646B-414F-866F-1DB1E5AD7194}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; Detect running instance to avoid file-in-use errors
AppMutex=UniversalSQLClientAppMutex
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
LicenseFile=license.txt
; Allow user to choose between 'All Users' (admin) and 'Current User' (lowest).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
UsePreviousPrivileges=no
OutputDir=dist
OutputBaseFilename=Universal_SQL_Client_WINDOWS_{#MyAppVersion}_setup
SetupIconFile=assets\app_icon.ico
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
ConfirmUninstall=Are you sure you want to uninstall %1?

; Running application prompts (replaces technical 'instances' jargon with clear instructions)
SetupAppRunningError=%1 is currently running.%n%nPlease close the application before continuing with the installation.%n%nClick OK to retry, or Cancel to exit.
UninstallAppRunningError=%1 is currently running.%n%nPlease close the application before continuing with the uninstallation.%n%nClick OK to retry, or Cancel to exit.
ErrorCloseApplications=Setup was unable to automatically close %1. Please close the application manually before continuing.

; Installation Scope dialog (Select Setup Install Mode)
PrivilegesRequiredOverrideTitle=Select Installation Scope
PrivilegesRequiredOverrideInstruction=Choose Installation Scope
PrivilegesRequiredOverrideText1=Choose whether %1 should be installed for all users on this machine or only for your account.
PrivilegesRequiredOverrideText2=Choose whether %1 should be installed only for your account or for all users on this computer.
PrivilegesRequiredOverrideCurrentUserRecommended=Install for &me only (recommended)%nInstalls to your local user profile. Does not require administrator privileges.
PrivilegesRequiredOverrideCurrentUser=Install for &me only%nInstalls to your local user profile. Does not require administrator privileges.
PrivilegesRequiredOverrideAllUsers=Install for &all users%nInstalls to Program Files. Available to all accounts on this PC (requires administrator privileges).
PrivilegesRequiredOverrideAllUsersRecommended=Install for &all users (recommended)%nInstalls to Program Files. Available to all accounts on this PC (requires administrator privileges).

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; PyInstaller output — includes all Python runtime, app code, assets, ui, pg_client, etc.
Source: "dist\Universal SQL Client\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Databases folder (may contain writable user data; kept separate from PyInstaller output)
Source: "databases\*"; DestDir: "{app}\databases"; Flags: ignoreversion recursesubdirs createallsubdirs
; Assets folder (icons, images; kept separate so icon paths resolve correctly at install time)
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
; Oracle Instant Client — shipped via installer to keep PyInstaller bundle lean
Source: "resources\oracle\instantclient\*"; DestDir: "{app}\resources\oracle\instantclient"; Flags: ignoreversion recursesubdirs createallsubdirs
; CData connector wheels (ServiceNow, CSV) — large binaries kept outside PyInstaller bundle
Source: "drivers\*"; DestDir: "{app}\drivers"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\app_icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  { The Inno Setup uninstall key that stores the install scope (All Users vs Current User). }
  { Deleting it ensures the All Users/Current User dialog is shown on the next fresh install. }
  UninstallKeyHKLM = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6A6E3F74-646B-414F-866F-1DB1E5AD7194}_is1';
  UninstallKeyHKCU = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6A6E3F74-646B-414F-866F-1DB1E5AD7194}_is1';
  { Uninstall options page layout constants (used by MakeRow and InitializeUninstallProgressForm) }
  ROW_H = 42;   { total row height in logical pixels }
  CHK_W = 18;   { checkbox square width              }
  GAP   = 6;    { gap between checkbox and label text }

var
  RemoveConnections: Boolean;
  RemoveSettings: Boolean;
  RemoveCreds: Boolean;
  ChkAll, Chk1, Chk2, Chk3: TNewCheckBox;
  UpdatingChecks: Boolean;

procedure UpdateSelectAllState;
begin
  if not UpdatingChecks then
  begin
    UpdatingChecks := True;
    try
      ChkAll.Checked := Chk1.Checked and Chk2.Checked and Chk3.Checked;
    finally
      UpdatingChecks := False;
    end;
  end;
end;

procedure ChkAllOnClick(Sender: TObject);
begin
  if not UpdatingChecks then
  begin
    UpdatingChecks := True;
    try
      Chk1.Checked := ChkAll.Checked;
      Chk2.Checked := ChkAll.Checked;
      Chk3.Checked := ChkAll.Checked;
    finally
      UpdatingChecks := False;
    end;
  end;
end;

procedure ItemChkOnClick(Sender: TObject);
begin
  UpdateSelectAllState;
end;

function ParamEnabled(const Name: String): Boolean;
begin
  Result := ExpandConstant('{param:' + Name + '|0}') = '1';
end;

function InitializeUninstall(): Boolean;
begin
  { Interactive mode defaults to keep everything; the options page below
    lets the user opt in. Silent mode keeps everything unless the caller
    passes /REMOVEALL=1 or individual flags /REMOVECONNECTIONS=1 /REMOVESETTINGS=1 /REMOVECREDS=1. }
  if UninstallSilent and ParamEnabled('REMOVEALL') then
  begin
    RemoveConnections := True;
    RemoveSettings := True;
    RemoveCreds := True;
  end
  else
  begin
    RemoveConnections := UninstallSilent and ParamEnabled('REMOVECONNECTIONS');
    RemoveSettings := UninstallSilent and ParamEnabled('REMOVESETTINGS');
    RemoveCreds := UninstallSilent and ParamEnabled('REMOVECREDS');
  end;
  Result := True;
end;

{ ──────────────────────────────────────────────────────────────────────────── }
{ Helper: thin horizontal divider (1 px bevel line)                           }
{ ──────────────────────────────────────────────────────────────────────────── }
procedure MakeDivider(AParent: TWinControl; ALeft, ATop, AWidth: Integer);
var
  Bvl: TBevel;
begin
  Bvl := TBevel.Create(UninstallProgressForm);
  Bvl.Parent := AParent;
  Bvl.Left := ALeft;
  Bvl.Top := ATop;
  Bvl.Width := AWidth;
  Bvl.Height := 1;
  Bvl.Shape := bsTopLine;
end;

{ ──────────────────────────────────────────────────────────────────────────── }
{ Helper: small uppercase section-category label (e.g. "YOUR DATA")           }
{ ──────────────────────────────────────────────────────────────────────────── }
function MakeSectionLabel(AParent: TWinControl; const ACaption: String;
  ALeft, ATop, AWidth: Integer): TNewStaticText;
var
  Lbl: TNewStaticText;
begin
  Lbl := TNewStaticText.Create(UninstallProgressForm);
  Lbl.Parent := AParent;
  Lbl.Left := ALeft;
  Lbl.Top := ATop;
  Lbl.Width := AWidth;
  Lbl.Height := ScaleY(16);
  Lbl.AutoSize := False;
  Lbl.ShowAccelChar := False;
  Lbl.Caption := ACaption;
  Lbl.Font.Size := 7;
  Lbl.Font.Color := $9AA0A6;  { Google #9AA0A6 medium-gray }
  Result := Lbl;
end;

{ ──────────────────────────────────────────────────────────────────────────── }
{ Helper: flat checkbox row — bold label + muted description, no box border   }
{   AParent  : the notebook page                                               }
{   ALeft    : left edge of the checkbox control                               }
{   ATop     : top of the row                                                  }
{   AWidth   : usable width for labels (right of checkbox)                    }
{   Returns  : the TNewCheckBox so caller can assign Chk1/2/3                 }
{ ──────────────────────────────────────────────────────────────────────────── }
function MakeRow(AParent: TWinControl;
  const ALabelText, ADescText: String;
  ALeft, ATop, AWidth: Integer;
  AEnabled: Boolean): TNewCheckBox;
var
  Chk: TNewCheckBox;
  LabelCtl, DescCtl: TNewStaticText;
  TextLeft, TextWidth: Integer;
begin
  TextLeft  := ALeft + ScaleX(CHK_W + GAP);
  TextWidth := AWidth - ScaleX(CHK_W + GAP);

  { Checkbox: vertically centred in the row }
  Chk := TNewCheckBox.Create(UninstallProgressForm);
  Chk.Parent := AParent;
  Chk.Left := ALeft;
  Chk.Top := ATop + ScaleY((ROW_H - 14) div 2);  { ~centre }
  Chk.Width := ScaleX(CHK_W);
  Chk.Caption := '';      { caption is blank; text is separate labels }
  Chk.Checked := False;
  Chk.Enabled := AEnabled;

  { Bold primary label }
  LabelCtl := TNewStaticText.Create(UninstallProgressForm);
  LabelCtl.Parent := AParent;
  LabelCtl.Left := TextLeft;
  LabelCtl.Top := ATop + ScaleY(6);
  LabelCtl.Width := TextWidth;
  LabelCtl.Height := ScaleY(16);
  LabelCtl.AutoSize := False;
  LabelCtl.ShowAccelChar := False;
  LabelCtl.Caption := ALabelText;
  LabelCtl.Font.Style := [fsBold];
  LabelCtl.Font.Size := 9;
  LabelCtl.Font.Color := $202124;  { Google near-black }

  { Muted description }
  DescCtl := TNewStaticText.Create(UninstallProgressForm);
  DescCtl.Parent := AParent;
  DescCtl.Left := TextLeft;
  DescCtl.Top := LabelCtl.Top + ScaleY(18);
  DescCtl.Width := TextWidth;
  DescCtl.Height := ScaleY(16);
  DescCtl.AutoSize := False;
  DescCtl.ShowAccelChar := False;
  DescCtl.Caption := ADescText;
  DescCtl.Font.Size := 8;
  DescCtl.Font.Color := $5F6368;  { Google medium-gray }

  Result := Chk;
end;

{ ──────────────────────────────────────────────────────────────────────────── }
{ Main uninstall options page — Google Material flat style                     }
{ ──────────────────────────────────────────────────────────────────────────── }
procedure InitializeUninstallProgressForm();
var
  Page: TNewNotebookPage;
  GoButton: TNewButton;
  BL, BT, BW, CurY: Integer;
  SecLbl: TNewStaticText;
  ChkApp: TNewCheckBox;
  OrigName, OrigDesc: String;
  OrigCancelEnabled: Boolean;
  OrigCancelModal: Integer;
begin
  if UninstallSilent then
    Exit;

  BT := UninstallProgressForm.StatusLabel.Top;
  BL := UninstallProgressForm.StatusLabel.Left;
  BW := UninstallProgressForm.StatusLabel.Width;

  { ── inner notebook page ─────────────────────────────────────────────── }
  Page := TNewNotebookPage.Create(UninstallProgressForm);
  Page.Notebook := UninstallProgressForm.InnerNotebook;
  Page.Parent := UninstallProgressForm.InnerNotebook;
  Page.Align := alClient;
  UninstallProgressForm.InnerNotebook.ActivePage := Page;

  CurY := BT;

  { ── Section: APPLICATION FILES ─────────────────────────────────────── }
  SecLbl := MakeSectionLabel(Page, 'APPLICATION FILES', BL, CurY, BW);
  CurY := SecLbl.Top + SecLbl.Height + ScaleY(4);

  { Required app-files row (disabled, always checked) }
  ChkApp := MakeRow(Page,
    'Universal SQL Client',
    'Required  ·  Cannot be deselected',
    BL, CurY, BW, False);
  ChkApp.Checked := True;
  CurY := CurY + ScaleY(ROW_H);

  MakeDivider(Page, BL, CurY, BW);
  CurY := CurY + ScaleY(14);

  { ── Section: YOUR DATA ──────────────────────────────────────────────── }
  SecLbl := MakeSectionLabel(Page, 'YOUR DATA', BL, CurY, BW);

  ChkAll := TNewCheckBox.Create(UninstallProgressForm);
  ChkAll.Parent := Page;
  ChkAll.Caption := 'Select all';
  ChkAll.Font.Size := 8;
  ChkAll.Font.Color := $5F6368;
  ChkAll.Cursor := crHandPoint;
  ChkAll.Left := BL + BW - ScaleX(85);
  ChkAll.Top := CurY - ScaleY(1);
  ChkAll.Width := ScaleX(85);
  ChkAll.Height := ScaleY(16);
  ChkAll.OnClick := @ChkAllOnClick;

  CurY := SecLbl.Top + SecLbl.Height + ScaleY(4);

  Chk1 := MakeRow(Page,
    'Saved Connections & Query History',
    'Database connections, workspaces, and query logs',
    BL, CurY, BW, True);
  Chk1.OnClick := @ItemChkOnClick;
  CurY := CurY + ScaleY(ROW_H);
  MakeDivider(Page, BL, CurY, BW);
  CurY := CurY + ScaleY(2);

  Chk2 := MakeRow(Page,
    'Application Settings & Preferences',
    'User preferences, appearance themes, and console history',
    BL, CurY, BW, True);
  Chk2.OnClick := @ItemChkOnClick;
  CurY := CurY + ScaleY(ROW_H);
  MakeDivider(Page, BL, CurY, BW);
  CurY := CurY + ScaleY(2);

  Chk3 := MakeRow(Page,
    'Stored Passwords & Credentials',
    'Saved database passwords and authentication tokens',
    BL, CurY, BW, True);
  Chk3.OnClick := @ItemChkOnClick;

  { ── footer buttons ───────────────────────────────────────────────────── }
  GoButton := TNewButton.Create(UninstallProgressForm);
  GoButton.Parent := UninstallProgressForm;
  GoButton.Left := UninstallProgressForm.CancelButton.Left
    - UninstallProgressForm.CancelButton.Width - ScaleX(10);
  GoButton.Top := UninstallProgressForm.CancelButton.Top;
  GoButton.Width := UninstallProgressForm.CancelButton.Width;
  GoButton.Height := UninstallProgressForm.CancelButton.Height;
  GoButton.Caption := 'Uninstall';
  GoButton.ModalResult := mrOk;
  GoButton.TabOrder := UninstallProgressForm.CancelButton.TabOrder;
  UninstallProgressForm.CancelButton.TabOrder := GoButton.TabOrder + 1;

  { ── show the page modally ────────────────────────────────────────────── }
  OrigName := UninstallProgressForm.PageNameLabel.Caption;
  OrigDesc := UninstallProgressForm.PageDescriptionLabel.Caption;
  OrigCancelEnabled := UninstallProgressForm.CancelButton.Enabled;
  OrigCancelModal := UninstallProgressForm.CancelButton.ModalResult;

  UninstallProgressForm.PageNameLabel.Caption := 'Uninstall {#MyAppName}';
  UninstallProgressForm.PageDescriptionLabel.Caption :=
    'Choose what to remove before uninstalling';
  UninstallProgressForm.CancelButton.Enabled := True;
  UninstallProgressForm.CancelButton.ModalResult := mrCancel;

  if UninstallProgressForm.ShowModal = mrCancel then
    Abort;

  RemoveConnections := Chk1.Checked;
  RemoveSettings := Chk2.Checked;
  RemoveCreds := Chk3.Checked;

  { Restore form state for the actual uninstall-progress phase }
  GoButton.Visible := False;
  UninstallProgressForm.PageNameLabel.Caption := OrigName;
  UninstallProgressForm.PageDescriptionLabel.Caption := OrigDesc;
  UninstallProgressForm.CancelButton.Enabled := OrigCancelEnabled;
  UninstallProgressForm.CancelButton.ModalResult := OrigCancelModal;
  UninstallProgressForm.InnerNotebook.ActivePage :=
    UninstallProgressForm.InstallingPage;
end;

procedure DeleteCredential(Target: String);
var
  ResultCode: Integer;
begin
  Exec('cmdkey.exe', '/delete:"' + Target + '"', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
end;

procedure DeleteAllStoredCredentials();
var
  ResultCode: Integer;
  PsCmd: String;
begin
  // Delete known static targets
  DeleteCredential('Universal SQL Client');
  DeleteCredential('access_token@Universal SQL Client');
  DeleteCredential('refresh_token@Universal SQL Client');
  DeleteCredential('user@Universal SQL Client');
  DeleteCredential('avatar@Universal SQL Client');
  DeleteCredential('DB Explorer');
  DeleteCredential('DB_Explorer_Credentials');
  DeleteCredential('QtDBExplorer');

  // Purge any dynamic keyring credentials matching Universal SQL Client or DB Explorer
  PsCmd := '-NoProfile -NonInteractive -Command "cmdkey /list | Select-String ''target=(.*(Universal SQL Client|DB Explorer|QtDBExplorer).*)'' | ForEach-Object { $t = $_.Matches[0].Groups[1].Value.Trim(); cmdkey /delete:\"$t\" }"';
  Exec('powershell.exe', PsCmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

var
  UninstallSuccessful: Boolean;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if RemoveConnections then
    begin
      Log('Uninstall: deleting %APPDATA%\Universal SQL Client');
      DelTree(ExpandConstant('{userappdata}\Universal SQL Client'), True, True, True);
    end;
    if RemoveSettings then
    begin
      Log('Uninstall: deleting %APPDATA%\DBExplorer and HKCU\Software\DBExplorer');
      DelTree(ExpandConstant('{userappdata}\DBExplorer'), True, True, True);
      RegDeleteKeyIncludingSubkeys(HKCU, 'Software\DBExplorer');
    end;
    if RemoveCreds then
    begin
      Log('Uninstall: deleting stored credentials');
      DeleteAllStoredCredentials();
    end;
  end
  else if CurUninstallStep = usPostUninstall then
  begin
    UninstallSuccessful := True;
  end;
end;

procedure DeinitializeUninstall;
begin
  if UninstallSuccessful then
  begin
    RegDeleteKeyIncludingSubkeys(HKLM, UninstallKeyHKLM);
    RegDeleteKeyIncludingSubkeys(HKCU, UninstallKeyHKCU);
  end;
end;
