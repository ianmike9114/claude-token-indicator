# Claude Token Indicator

![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/runtime%20deps-none-success)
![Built with PyInstaller](https://img.shields.io/badge/build-PyInstaller-FFD343)
![License](https://img.shields.io/badge/license-MIT-blue)

A slim, always-on-top strip for Windows that shows your Claude **session (5h)**
and **weekly (7d)** usage at a glance — the same numbers as the desktop app's
**Settings → Plan usage limits** panel, pinned next to your other tray/overlay
indicators.

![Screenshot of the indicator strip](assets/screenshot.png)

> Session and Weekly usage as mini bars with percentages and reset countdowns;
> hover for the ✕ quit button. *(Real capture of the running strip.)*

## How it works

It reads the OAuth token that Claude Code already stores at
`~/.claude/.credentials.json`, then calls the same undocumented endpoint the
`/usage` command uses:

```
GET https://api.anthropic.com/api/oauth/usage
```

If the stored token is expired, it refreshes it (and writes the new token back
so Claude Code stays in sync). No separate login is required — but you must have
signed in with Claude Code at least once. **Nothing is sent anywhere except
`console.anthropic.com` and `api.anthropic.com`. The token is never logged.**

## Requirements

- Windows 10/11
- Python 3.10+ (with tkinter, which ships with the standard Windows installer)
- No third-party packages for running from source

## Run from source

```bash
python main.py
```

A thin bar appears at the top-center of your screen.

- **Left-drag** the bar to reposition it (the position is remembered).
- **Right-click** for `Refresh now`, `Reset position`, and `Quit`.

## Configuration

Edit `config.json` (created next to `main.py` on first drag/save):

| Key | Default | Meaning |
|-----|---------|---------|
| `poll_seconds` | `180` | How often to refresh (min 60; the endpoint is rate-limited). |
| `position` | `top-center` | `top-center`, `top-right`, or `top-left`. |
| `offset_x` / `offset_y` | `null` | Exact pixel position (set by dragging). |
| `show_weekly` | `true` | Show the weekly segment. |
| `warn_threshold` | `60` | Percent at which a bar turns amber. |
| `crit_threshold` | `85` | Percent at which a bar turns red. |

## Install (recommended)

Double-click **`Install.bat`** (or run `powershell -ExecutionPolicy Bypass -File installer\install.ps1`). No admin rights needed. It:

- builds `ClaudeTokenIndicator.exe`,
- installs it to `%LOCALAPPDATA%\ClaudeTokenIndicator`,
- adds Start Menu + Startup shortcuts (auto-start at login),
- registers an entry in **Settings → Apps** for clean removal,
- launches the app.

Uninstall from **Settings → Apps**, or run `%LOCALAPPDATA%\ClaudeTokenIndicator\uninstall.ps1`.

## Build a standalone .exe

```bash
powershell -ExecutionPolicy Bypass -File build.ps1
```

Produces `dist\ClaudeTokenIndicator.exe` — a single file that runs with no
Python install and no console window.

## Start automatically with Windows

**Option A — Startup folder (simplest):**
1. Press `Win+R`, type `shell:startup`, press Enter.
2. Put a shortcut to `ClaudeTokenIndicator.exe` (or a `.bat` that runs
   `pythonw main.py`) in that folder.

**Option B — registry Run key:**
```powershell
Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' `
  -Name 'ClaudeTokenIndicator' `
  -Value '"C:\path\to\ClaudeTokenIndicator.exe"'
```

## Troubleshooting

- **"Claude auth expired — open Claude Code":** your refresh token is no longer
  valid. Open Claude Code (or the desktop app) and it will re-authenticate;
  the indicator picks up the refreshed token automatically.
- **Bar shows greyed-out / stale values:** a transient network error or a `429`
  rate-limit from the usage endpoint. It keeps showing the last good numbers and
  retries with backoff.

## Notes

The usage endpoint and its response fields are undocumented and may change.
Parsing is defensive, but if Anthropic changes the shape the numbers may need a
small update in `claude_indicator/usage.py`.
