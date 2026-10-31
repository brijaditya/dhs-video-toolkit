<#
  DHS video toolkit - one-time setup for Windows.
  Right-click this file > "Run with PowerShell", or in a PowerShell window:
      powershell -ExecutionPolicy Bypass -File C:\DHS\setup.ps1
  Safe to run again at any time. It ends with READY or a clear error.
#>
$ErrorActionPreference = 'Continue'   # program errors are checked one by one below
$ProgressPreference = 'SilentlyContinue'
$Root = $PSScriptRoot
Set-Location $Root

function Say($msg)  { Write-Host "  $msg" }
function Step($msg) { Write-Host ""; Write-Host "== $msg" -ForegroundColor Cyan }
function Stop-Setup($cause, $fix) {
    Write-Host ""
    Write-Host "PROBLEM: $cause" -ForegroundColor Red
    Write-Host "FIX: $fix" -ForegroundColor Yellow
    exit 1
}
function Update-SessionPath {
    # pick up programs that were just installed, without reopening the window
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}
function Has-Command($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Install-WithWinget($id, $label) {
    if (-not (Has-Command winget)) {
        Stop-Setup "$label is missing and Windows 'winget' is not available to install it." "Open the Microsoft Store, update 'App Installer', then run setup.ps1 again."
    }
    Say "Installing $label (this can take a few minutes)..."
    & winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    # winget returns non-zero when the program is already there; the check after decides success
    Update-SessionPath
}
function Run-Checked($label, [scriptblock]$cmd) {
    & $cmd
    if ($LASTEXITCODE -ne 0) { Stop-Setup "$label did not finish." "Check your internet connection, then run setup.ps1 again." }
}

try {
    Write-Host "DHS video toolkit setup" -ForegroundColor Green
    Write-Host "Folder: $Root"

    # ---------------------------------------------------------------- Git
    Step "1/7  Git"
    if (-not (Has-Command git)) { Install-WithWinget 'Git.Git' 'Git' }
    if (-not (Has-Command git)) {
        $g = "$env:ProgramFiles\Git\cmd"
        if (Test-Path "$g\git.exe") { $env:Path += ";$g" }
    }
    if (-not (Has-Command git)) { Stop-Setup "Git could not be installed." "Install it from https://git-scm.com/download/win, then run setup.ps1 again." }
    Say "Git OK"

    # ---------------------------------------------------------------- FFmpeg
    Step "2/7  FFmpeg"
    if (-not ((Has-Command ffmpeg) -and (Has-Command ffprobe))) { Install-WithWinget 'Gyan.FFmpeg' 'FFmpeg' }
    if (-not ((Has-Command ffmpeg) -and (Has-Command ffprobe))) {
        # winget sometimes needs a new window for PATH; look in its folder directly
        $found = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { $env:Path += ";$($found.DirectoryName)" }
    }
    if (-not ((Has-Command ffmpeg) -and (Has-Command ffprobe))) { Stop-Setup "FFmpeg could not be found after installing." "Close this window, open a new PowerShell window and run setup.ps1 again." }
    Say "FFmpeg OK"

    # ---------------------------------------------------------------- Python 3.12
    Step "3/7  Python 3.12"
    function Find-Python312 {
        if (Has-Command py) {
            $p = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $p) { return $p.Trim() }
        }
        foreach ($c in @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "$env:ProgramFiles\Python312\python.exe")) {
            if (Test-Path $c) { return $c }
        }
        return $null
    }
    $py = Find-Python312
    if (-not $py) { Install-WithWinget 'Python.Python.3.12' 'Python 3.12'; $py = Find-Python312 }
    if (-not $py) { Stop-Setup "Python 3.12 could not be found after installing." "Close this window, open a new PowerShell window and run setup.ps1 again." }
    Say "Python OK: $py"

    # ---------------------------------------------------------------- toolkit venv
    Step "4/7  Toolkit Python environment"
    $venvPy = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) { Run-Checked "Creating the Python environment" { & $py -m venv (Join-Path $Root '.venv') } }
    Run-Checked "Updating pip" { & $venvPy -m pip install --quiet --upgrade pip }
    Say "Installing faster-whisper, auto-editor, OpenCV, numpy... (first time takes a few minutes)"
    Run-Checked "Installing the Python packages" { & $venvPy -m pip install --quiet -r (Join-Path $Root 'requirements.txt') }
    # auto-editor downloads its engine the first time it runs; do that now
    $ae = Join-Path $Root '.venv\Scripts\auto-editor.exe'
    Run-Checked "Preparing auto-editor" { & $ae --version | Out-Null }
    & $venvPy -c "import faster_whisper, cv2, numpy, PIL, fontTools; print('imports ok')" | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-Setup "Some Python packages did not install correctly." "Delete the .venv folder inside $Root and run setup.ps1 again." }
    Say "Python packages OK"

    Say "Downloading the speech model (about 500 MB, once)..."
    & $venvPy -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')" 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Host "  Could not download it now. It will download the first time you transcribe a video (needs internet)." -ForegroundColor Yellow }
    else { Say "Speech model OK" }

    # ---------------------------------------------------------------- effects skill
    Step "5/7  Effects skill"
    # The effects skill is part of this toolkit (.claude\skills\effects). Its own setup.sh does not work on Windows
    # (it expects .venv/bin/python), so build its environment the Windows way.
    $effects = Join-Path $Root '.claude\skills\effects'
    if (-not (Test-Path (Join-Path $effects 'scripts\fx.py'))) {
        Stop-Setup "The effects skill files are missing from $effects." "Copy the whole toolkit folder again (it must include .claude\skills\effects), then run setup.ps1."
    }
    $fxPy = Join-Path $effects '.venv\Scripts\python.exe'
    if (-not (Test-Path $fxPy)) { Run-Checked "Creating the effects environment" { & $py -m venv (Join-Path $effects '.venv') } }
    Run-Checked "Updating pip (effects)" { & $fxPy -m pip install --quiet --upgrade pip }
    Say "Installing the effects packages (mediapipe is large, please wait)..."
    Run-Checked "Installing the effects packages" { & $fxPy -m pip install --quiet -r (Join-Path $effects 'requirements.txt') faster-whisper }
    & $fxPy -c "import mediapipe, cv2, PIL, numpy; print('ok')" | Out-Null
    if ($LASTEXITCODE -ne 0) { Stop-Setup "The effects skill packages did not install correctly." "Delete the folder $effects\.venv and run setup.ps1 again." }
    Say "Effects skill OK (uses $fxPy)"

    # ---------------------------------------------------------------- folders
    Step "6/7  Folders"
    foreach ($d in @('clients', 'templates')) { New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null }
    Say "clients\ and templates\ are ready"

    # ---------------------------------------------------------------- self-test
    Step "7/7  Self-test (30 seconds)"
    & $venvPy (Join-Path $Root 'selftest.py')
    if ($LASTEXITCODE -ne 0) { Stop-Setup "The self-test failed (see the table above)." "Run setup.ps1 again. If it still fails, tell Claude Code: 'setup self-test failed'." }

    Write-Host ""
    Write-Host "READY - the DHS video toolkit is installed." -ForegroundColor Green
    Write-Host "Next: open Claude Code in $Root and say: 'New client <name>, here is the video.'"
    exit 0
}
catch {
    Stop-Setup "Setup stopped: $($_.Exception.Message)" "Run setup.ps1 again. If it repeats, send this message to Claude Code."
}
