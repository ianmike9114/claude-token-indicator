<#
Uninstaller for Claude Token Indicator. Removes shortcuts, the install folder,
and the uninstall registry entry. Stops the running app first. No admin needed.
#>

$ErrorActionPreference = "SilentlyContinue"

$AppName     = "ClaudeTokenIndicator"
$DisplayName = "Claude Token Indicator"
$InstallDir  = Join-Path $env:LOCALAPPDATA $AppName

# Stop the running process.
Get-Process -Name $AppName | Stop-Process -Force

# Remove shortcuts.
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$DisplayName.lnk"
$Startup   = Join-Path ([Environment]::GetFolderPath("Startup")) "$DisplayName.lnk"
Remove-Item $StartMenu, $Startup -Force

# Remove uninstall registry entry.
Remove-Item "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppName" -Recurse -Force

# Remove install folder (schedule self-delete since uninstall.ps1 lives inside).
Start-Process powershell -ArgumentList @(
    "-NoProfile","-WindowStyle","Hidden","-Command",
    "Start-Sleep 1; Remove-Item -Recurse -Force `"$InstallDir`""
)

Write-Host "$DisplayName uninstalled."
