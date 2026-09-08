# VideoBridge Windows build script
# Must be run on Windows. PyInstaller does not cross-compile.

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$AppName = "VideoBridge"
$ResourceBin = Join-Path (Get-Location) "resources/bin"

Write-Host "==> Checking external binaries..." -ForegroundColor Cyan
$required = @("ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe", "whisper-cli.exe")
$missing = @()
foreach ($name in $required) {
    if (-not (Test-Path (Join-Path $ResourceBin $name))) {
        $missing += $name
    }
}
if ($missing.Count -gt 0) {
    Write-Host "Missing required Windows binaries in resources/bin:" -ForegroundColor Red
    foreach ($name in $missing) {
        Write-Host "  - $name" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "Suggested sources:" -ForegroundColor Yellow
    Write-Host "  ffmpeg/ffprobe : https://www.gyan.dev/ffmpeg/builds/"
    Write-Host "  yt-dlp          : https://github.com/yt-dlp/yt-dlp/releases"
    Write-Host "  whisper-cli     : whisper.cpp Windows build"
    exit 1
}

Write-Host "==> Creating virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\pip.exe install -e ".[dev]" pyinstaller

Write-Host "==> Running PyInstaller..." -ForegroundColor Cyan
& .venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --name $AppName `
    --windowed `
    --add-data "resources/bin;resources/bin" `
    app/main.py

Write-Host ""
Write-Host "Build complete: dist\$AppName\" -ForegroundColor Green
Write-Host "Optional: use Inno Setup or NSIS to create an installer from dist\$AppName." -ForegroundColor Cyan
