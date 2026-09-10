# VideoBridge 上下文交接（压缩版）

> 用途：新会话/新成员快速接手。详细历史见 git log。

## 0. 一句话
本地桌面视频工具：**搬运 → 去重 → 字幕 →（可选）配音**，纯本地、无服务端。

## 1. 环境
- 项目：`/Volumes/ExtDrive/视频处理/video-bridge`
- 远端：`https://github.com/coolSummer003/video-bridge.git`（`main`）
- 技术：Python 3.12 + PySide6-Essentials + playwright
- 依赖外部程序：ffmpeg-full（libass）、yt-dlp、whisper-cli
- `gh` 已登录（coolSummer003，keyring）
- 注意：`artifacts/`、`models/`、`resources/bin/` 已 gitignore，勿提交

## 2. 页面
默认页签：**下载 / 去重 / 字幕**
配音页默认隐藏，`VIDEO_BRIDGE_SHOW_DUB=1` 显示。

## 3. 模块现状
### 下载 `app/core/`
- `platforms.py`：从分享文本提取链接 `extract_video_url`；平台识别 `detect_platform`
- 抖音：`douyin_browser.py` — Playwright 打开视频页，拦截 `douyinvod.com` 真实视频流下载。**无需 Cookie**，已验证
- 其他平台：`downloader.py` — yt-dlp
- 抖音 Cookie/扫码登录（`douyin_cookie.py` / `douyin_login.py`）保留但 UI 已隐藏

### 去重 `app/core/dedup.py` + `dedup_advanced.py`
一键操作：选视频 → 开始去重。
- 结构处理（默认开）：3 段闪白转场 + 竖屏自动模糊拓边（→1280x720）
- 滤镜：镜像**默认关**、饱和度/对比度、缩放裁切、色调、噪点、模糊、随机参数；强度 轻/中/重
- 隐形二创（选素材 B）：7:1 抽帧混合（240fps）+ 全屏 3% 隐形混合（滑杆 1–7%）

### 字幕 `app/core/subtitle.py` + `model_downloader.py`
- whisper-cli 生成 SRT，默认烧录 `*.subbed.mp4`
- 模型下载：ModelScope（`iceCream2025/whisper.cpp`）优先 → hf-mirror 备用
- 语言下拉；SRT 解析 `parse_srt` / 纯文本 `extract_subtitle_text`

### 配音（隐藏）`app/core/audio8.py` + `audio8_bootstrap.py` + `dubbing.py`
- Audio8 TTS 0.1B ONNX INT8（ModelScope `Audio8/audio8-TTS-0.1B-ONNX-INT8`）
- 首次自动：克隆 `onnx_runtime_0_1b_int8` → setup 依赖 → 下载模型 → 建内置 `default` 音色 → 启动 127.0.0.1:8024
- 支持注册新音色、音色下拉、SRT 时间轴逐句同步配音、替换视频原声

## 4. 关键修复（勿回退）
- `config.py`：开发态用 Homebrew 二进制；仅打包态用 `resources/bin`
- 字幕烧录：先校验 SRT 非空，再复制到临时安全路径（避免路径转义/退出码 183）
- 隐形混合必须是 `blend=all_expr='A*0.97+B*0.03'`；`all_mode=normal` 会把素材完全盖住
- `xfade` 转场会缩短时长，段长按 `seg_len=(D+(n-1)d)/n`、`step=seg_len-d` 补偿
- `dedup_pip` / `dedup_frame_mix` 统一尺寸/SAR/帧率，并加 `-t duration` 防卡死
- Cookie `expires=-1` → 写 `0`（会话 Cookie）

## 5. 待办
1. `douyin_browser.py` 加浏览器回退（打包版无 Chromium）：
   依次尝试 内置 chromium → `channel="chrome"` → `channel="msedge"`
2. 打 Windows 包（GitHub Actions）：
   ```bash
   gh workflow run build-windows.yml --repo coolSummer003/video-bridge
   gh run list --repo coolSummer003/video-bridge --workflow build-windows.yml
   gh run download <run-id> -n VideoBridge-Windows --repo coolSummer003/video-bridge -D artifacts/windows
   ```
3. 如需：macOS `.dmg` 打包 / 签名公证

## 6. 常用命令
```bash
cd "/Volumes/ExtDrive/视频处理/video-bridge"
source .venv/bin/activate
python -m app.main        # 启动
python -m pytest -q       # 测试（当前 5 项）
```
