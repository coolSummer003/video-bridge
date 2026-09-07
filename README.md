# VideoBridge

基于开源组件搭建的 macOS 本地视频处理 MVP：

- 下载：yt-dlp
- 字幕：whisper.cpp (`whisper-cli`)
- 去重/二创：FFmpeg

目标：最终打包成一个 macOS `.app`，用户安装后无需安装 Python / FFmpeg / yt-dlp / whisper。

## 三个独立模块

桌面端按功能拆成三个独立页签，不做一键串联处理：

1. 下载：粘贴链接 → yt-dlp 下载到本地目录
2. 字幕：选择本地视频 → whisper.cpp 生成 SRT；默认同时烧录字幕到视频画面，输出 `*.subbed.mp4`；首次使用时若无模型会自动提示下载
3. 去重：选择本地视频 → 可选抽帧混合、随机片段重排、画中画、滤镜参数变体、BGM 叠加，输出强差异新视频

## 开发运行

```bash
# 1. 准备依赖
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. 下载字幕模型（也可以不手动下载，桌面端首次生成字幕时会自动提示下载）
scripts/download_model.sh ggml-small.bin

# 3. 启动桌面端
python -m app.main
```

> 运行前需要本机有 `ffmpeg`、`ffprobe`、`yt-dlp`、`whisper-cli`。
> 也可以设置 `FFMPEG_PATH / FFPROBE_PATH / YTDLP_PATH / WHISPER_CLI_PATH` 指向自带的二进制。

## Windows 打包

> 当前项目在 macOS 上开发，PyInstaller 不支持在 macOS 直接生成 Windows exe。  
> Windows 安装包必须在 Windows 机器或 GitHub Actions Windows Runner 上构建。

1. 在 Windows 准备 `resources/bin/`：
   - `ffmpeg.exe`
   - `ffprobe.exe`
   - `yt-dlp.exe`
   - `whisper-cli.exe`
2. 运行：
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
   ```
3. 产物在 `dist\VideoBridge\`

## GitHub Actions 自动打包 Windows

仓库已包含：

```text
.github/workflows/build-windows.yml
```

触发方式：

- 手动触发：GitHub Actions 页面点 `Run workflow`
- 推送 tag：`git tag v0.1.0 && git push origin v0.1.0`

Workflow 会自动：

1. 在 `windows-latest` 上运行
2. 下载 ffmpeg / yt-dlp
3. 编译 whisper.cpp 生成 `whisper-cli.exe`
4. 安装 Python 依赖和 PyInstaller
5. 执行 Windows 打包
6. 上传 `VideoBridge-Windows` artifact

首次使用需要先把仓库推到 GitHub。

## 目录结构

```text
app/
  core/
    downloader.py   # yt-dlp 下载
    subtitle.py     # whisper-cli 字幕
    dedup.py        # ffmpeg 滤镜参数去重
    dedup_advanced.py # 双视频抽帧混合 / BGM 叠加
  ui/
    main_window.py    # PySide6 三个模块页签主窗口
  main.py
tests/
scripts/
  build_macos.sh        # PyInstaller 打包 .app
  download_model.sh     # 下载 whisper.cpp 模型
```
