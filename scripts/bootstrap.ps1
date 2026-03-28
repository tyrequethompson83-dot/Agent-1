param(
    [switch]$SkipPlaywright,
    [switch]$RunInit,
    [switch]$RunOnboard,
    [ValidateSet("home", "project")]
    [string]$InitStyle = "home"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -e .

if (-not $SkipPlaywright) {
    & ".\.venv\Scripts\python.exe" -m playwright install chromium
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

if ($RunInit) {
    & ".\.venv\Scripts\python.exe" -m agent1.main init --style $InitStyle
}

if ($RunOnboard) {
    & ".\.venv\Scripts\python.exe" -m agent1.main onboard --style $InitStyle --doctor-fix
}

Write-Output "Bootstrap complete. Activate venv with .\.venv\Scripts\activate"
