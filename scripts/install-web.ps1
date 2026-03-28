param(
    [string]$Repo = "tyrequethompson83-dot/Agent-1",
    [string]$Branch = "main",
    [ValidateSet("home", "project")]
    [string]$Style = "home",
    [string]$InstallDir = "",
    [switch]$SkipPlaywright,
    [switch]$SkipOnboard,
    [switch]$StartServices
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not $InstallDir) {
    $InstallDir = Join-Path $HOME "Agent-1"
}

$target = [System.IO.Path]::GetFullPath($InstallDir)
$installScript = Join-Path $target "scripts\install.ps1"

if (-not (Test-Path $target)) {
    New-Item -ItemType Directory -Path $target | Out-Null
}

$hasExistingRepo = (Test-Path $installScript)
if (-not $hasExistingRepo) {
    $existingEntries = Get-ChildItem -Force -LiteralPath $target
    if ($existingEntries.Count -gt 0) {
        throw "Install directory is not empty: $target"
    }

    $archiveUrl = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
    $tempRoot = Join-Path $env:TEMP ("agent1-install-" + [guid]::NewGuid().ToString("N"))
    $zipPath = Join-Path $tempRoot "agent1.zip"
    $extractRoot = Join-Path $tempRoot "extract"

    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    New-Item -ItemType Directory -Path $extractRoot | Out-Null

    try {
        Invoke-WebRequest -Uri $archiveUrl -OutFile $zipPath
        Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot -Force

        $expanded = Get-ChildItem -LiteralPath $extractRoot -Directory | Select-Object -First 1
        if (-not $expanded) {
            throw "Archive did not contain a repository folder."
        }

        Copy-Item -Path (Join-Path $expanded.FullName "*") -Destination $target -Recurse -Force
    }
    finally {
        if (Test-Path $tempRoot) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

if (-not (Test-Path $installScript)) {
    throw "Installer not found after download: $installScript"
}

$args = @(
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $installScript,
    "-Style",
    $Style
)

if ($SkipPlaywright) {
    $args += "-SkipPlaywright"
}

if ($SkipOnboard) {
    $args += "-SkipOnboard"
}

if ($StartServices) {
    $args += "-StartServices"
}

Write-Output "Installing Agent 1 into $target"
& powershell @args
