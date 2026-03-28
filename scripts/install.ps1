param(
    [ValidateSet("home", "project")]
    [string]$Style = "home",
    [switch]$SkipPlaywright,
    [switch]$SkipOnboard,
    [switch]$StartServices
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

if (-not $SkipOnboard) {
    $args = @("-m", "agent1.main", "onboard", "--style", $Style, "--doctor-fix")
    if ($StartServices) {
        $args += "--up"
    }
    & ".\.venv\Scripts\python.exe" @args
}

Write-Output "Install complete."
Write-Output "Next: .\\.venv\\Scripts\\python.exe -m agent1.main"
