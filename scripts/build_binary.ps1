param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -e ".[build]"

$distArgs = @(
    "--noconfirm",
    "--onefile",
    "--name", "agent1",
    "--paths", "src",
    "src/agent1/main.py"
)
if ($Clean) {
    $distArgs = @("--clean") + $distArgs
}

& $python -m PyInstaller @distArgs
Write-Output "Binary build complete: .\dist\agent1.exe"
