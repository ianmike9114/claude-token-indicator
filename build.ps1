# Build a single, no-console ClaudeTokenIndicator.exe with PyInstaller.
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

python -m pip install --upgrade pyinstaller

python -m PyInstaller `
    --noconsole `
    --onefile `
    --name ClaudeTokenIndicator `
    --icon "$PSScriptRoot\assets\icon.ico" `
    --add-data "$PSScriptRoot\assets\icon.ico;." `
    --clean `
    main.py

Write-Host ""
Write-Host "Built: $(Join-Path $PSScriptRoot 'dist\ClaudeTokenIndicator.exe')"
