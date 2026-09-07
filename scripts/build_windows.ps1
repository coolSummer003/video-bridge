# VideoBridge Windows 打包脚本
# 必须在 Windows 上运行（PyInstaller 不支持跨平台交叉编译）。
#
# 前置要求：
#   1. Windows 10/11
#   2. Python 3.12 已安装并加入 PATH
#   3. resources/bin 下准备好：
#        ffmpeg.exe
#        ffprobe.exe
#        yt-dlp.exe
#        whisper-cli.exe
#      如果缺失，脚本会给出提示并中止。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$AppName = "VideoBridge"
$ResourceBin = Join-Path (Get-Location) "resources/bin"

Write-Host "==> 检查外部二进制..." -ForegroundColor Cyan
$required = @("ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe", "whisper-cli.exe")
$missing = @()
foreach ($name in $required) {
    if (-not (Test-Path (Join-Path $ResourceBin $name))) {
        $missing += $name
    }
}
if ($missing.Count -gt 0) {
    Write-Host "缺少以下 Windows 二进制，请放入 resources/bin：" -ForegroundColor Red
    foreach ($name in $missing) {
        Write-Host "  - $name" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "建议来源：" -ForegroundColor Yellow
    Write-Host "  ffmpeg/ffprobe : https://www.gyan.dev/ffmpeg/builds/ (essentials 版即可)"
    Write-Host "  yt-dlp          : https://github.com/yt-dlp/yt-dlp/releases"
    Write-Host "  whisper-cli     : whisper.cpp 的 Windows 构建产物"
    exit 1
}

Write-Host "==> 创建虚拟环境..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\pip.exe install -e ".[dev]" pyinstaller

Write-Host "==> PyInstaller 打包..." -ForegroundColor Cyan
& .venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --name $AppName `
    --windowed `
    --add-data "resources/bin;resources/bin" `
    app/main.py

Write-Host ""
Write-Host "打包完成：dist\$AppName\" -ForegroundColor Green
Write-Host "如需生成安装包，可使用 Inno Setup / NSIS 将 dist\$AppName 打成 exe 安装程序。" -ForegroundColor Cyan
