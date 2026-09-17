<#
Per-user installer for Claude Token Indicator (no administrator rights needed).

  - Builds ClaudeTokenIndicator.exe with PyInstaller
  - Installs to %LOCALAPPDATA%\ClaudeTokenIndicator
  - Creates Start Menu + Startup shortcuts (auto-start on login)
  - Registers an entry in "Apps & features" so it can be uninstalled
  - Launches the app

Usage:
  powershell -ExecutionPolicy Bypass -File installer\install.ps1
  (or just double-click Install.bat)
#>

$ErrorActionPreference = "Stop"

$Root       = Split-Path $PSScriptRoot -Parent          # project root
$AppName    = "ClaudeTokenIndicator"
$DisplayName = "Claude Token Indicator"
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName
$ExeName    = "$AppName.exe"
$ExePath    = Join-Path $InstallDir $ExeName

Write-Host "Installing $DisplayName ..." -ForegroundColor Cyan

# --- 1. Build the exe --------------------------------------------------------
Push-Location $Root
try {
    python -m pip install --upgrade --quiet pyinstaller
    python -m PyInstaller --noconsole --onefile --clean --distpath build_dist `
        --workpath build_work --specpath build_work --name $AppName `
        --icon "$Root\assets\icon.ico" --add-data "$Root\assets\icon.ico;." main.py | Out-Null
    $BuiltExe = Join-Path $Root "build_dist\$ExeName"
    if (-not (Test-Path $BuiltExe)) { throw "Build failed: $ExeName not produced." }
}
finally { Pop-Location }

# --- 2. Copy into place ------------------------------------------------------
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item $BuiltExe $ExePath -Force

$IconSrc = Join-Path $Root "assets\icon.ico"
$IconDst = Join-Path $InstallDir "icon.ico"
if (Test-Path $IconSrc) { Copy-Item $IconSrc $IconDst -Force }
$IconRef = if (Test-Path $IconDst) { "$IconDst,0" } else { "$ExePath,0" }

# --- 3. Shortcuts (Start Menu + Startup) ------------------------------------
$WScript = New-Object -ComObject WScript.Shell

$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$sc = $WScript.CreateShortcut((Join-Path $StartMenu "$DisplayName.lnk"))
$sc.TargetPath = $ExePath
$sc.WorkingDirectory = $InstallDir
$sc.Description = $DisplayName
$sc.IconLocation = $IconRef
$sc.Save()

$Startup = [Environment]::GetFolderPath("Startup")
$scStart = $WScript.CreateShortcut((Join-Path $Startup "$DisplayName.lnk"))
$scStart.TargetPath = $ExePath
$scStart.WorkingDirectory = $InstallDir
$scStart.Description = "$DisplayName (auto-start)"
$scStart.IconLocation = $IconRef
$scStart.Save()

# --- 4. Register uninstall entry (per-user, no admin) ------------------------
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppName"
New-Item -Path $UninstallKey -Force | Out-Null
$UninstallCmd = "powershell -ExecutionPolicy Bypass -File `"$InstallDir\uninstall.ps1`""
Set-ItemProperty $UninstallKey DisplayName     $DisplayName
Set-ItemProperty $UninstallKey DisplayVersion  "0.1.0"
Set-ItemProperty $UninstallKey Publisher        "Self"
Set-ItemProperty $UninstallKey InstallLocation  $InstallDir
Set-ItemProperty $UninstallKey UninstallString  $UninstallCmd
Set-ItemProperty $UninstallKey NoModify 1 -Type DWord
Set-ItemProperty $UninstallKey NoRepair 1 -Type DWord

# Drop the uninstaller next to the exe so the entry above works.
Copy-Item (Join-Path $PSScriptRoot "uninstall.ps1") (Join-Path $InstallDir "uninstall.ps1") -Force

# --- 5. Launch ---------------------------------------------------------------
Start-Process $ExePath

Write-Host ""
Write-Host "Installed to $InstallDir" -ForegroundColor Green
Write-Host "Starts automatically at login. Running now." -ForegroundColor Green
Write-Host "Uninstall from Settings > Apps, or run: $InstallDir\uninstall.ps1"
