
"""PySide6 三个独立功能模块：下载 / 字幕 / 去重。"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.config import BinaryPaths
from ..core.dedup import DedupOptions, dedup_video, options_from_strength
from ..core.dedup_advanced import add_background_music, dedup_frame_mix, dedup_pip, dedup_random_segments
from ..core.downloader import download_video
from ..core.douyin_cookie import fetch_douyin_cookies
from ..core.douyin_login import douyin_login
from ..core.dubbing import RATES, replace_video_audio, text_to_speech, voice_options
from ..core.model_downloader import download_model
from ..core.platforms import detect_platform, extract_video_url, platform_options
from ..core.subtitle import burn_subtitles, generate_srt


class MainWindow(QMainWindow):
    append_log = Signal(str)
    task_finished = Signal(object)
    model_progress = Signal(int, int)
    model_ready = Signal(str)
    model_finished = Signal()
    douyin_login_done = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VideoBridge")
        self.resize(880, 620)
        self.append_log.connect(self._append_line)
        self.task_finished.connect(self._on_task_finished)
        self.task_finished.connect(lambda button: button.setEnabled(True))
        self.model_progress.connect(self._on_model_progress)
        self.model_ready.connect(self._on_model_ready)
        self.model_finished.connect(self._on_model_finished)
        self.douyin_login_done.connect(self._on_douyin_login_done)
        self._douyin_cookie_path: str | None = None
        self._build_ui()
        self._init_model_state()

    def _build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        title = QLabel("VideoBridge")
        title.setObjectName("appTitle")
        subtitle = QLabel("本地视频搬运 · 字幕 · 去重工作台")
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_download_tab(), "下载")
        self.tabs.addTab(self._build_dedup_tab(), "去重")
        self.tabs.addTab(self._build_dub_tab(), "配音")
        self.tabs.addTab(self._build_subtitle_tab(), "字幕")
        layout.addWidget(self.tabs, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(180)
        layout.addWidget(self.log_view)

        self.setCentralWidget(root)

    # ---------- 下载模块 ----------
    def _build_download_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(4, 8, 4, 4)
        group = QGroupBox("下载")
        form = QFormLayout(group)
        form.setContentsMargins(20, 30, 20, 20)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        outer.addWidget(group)
        outer.addStretch(1)

        self.download_url = QTextEdit()
        self.download_url.setPlaceholderText("粘贴抖音 / Bilibili 分享文本或视频链接\n例如：https://v.douyin.com/xxxx/ 复制此链接，打开Dou音搜索…")
        self.download_url.setMinimumHeight(78)
        self.download_url.textChanged.connect(self._refresh_download_url)
        form.addRow("分享文本", self.download_url)

        self.download_url_clean = QLineEdit()
        self.download_url_clean.setReadOnly(True)
        self.download_url_clean.setPlaceholderText("自动解析出的视频链接")
        form.addRow("解析链接", self.download_url_clean)

        self.download_platform = QComboBox()
        for label, code in platform_options():
            self.download_platform.addItem(label, code)
        self.download_platform.setCurrentIndex(0)
        form.addRow("平台", self.download_platform)

        self.douyin_login_widget = QWidget()
        douyin_row = QHBoxLayout(self.douyin_login_widget)
        douyin_row.setContentsMargins(0, 0, 0, 0)
        douyin_label = QLabel("抖音视频需要 Cookie，请先获取：")
        self.btn_douyin_login = QPushButton("抖音扫码登录 / 获取 Cookie")
        self.btn_douyin_login.setProperty("secondary", True)
        self.btn_douyin_login.clicked.connect(self._run_douyin_login)
        douyin_row.addWidget(douyin_label)
        douyin_row.addWidget(self.btn_douyin_login)
        douyin_row.addStretch(1)
        self.douyin_login_widget.hide()
        form.addRow("抖音 Cookie", self.douyin_login_widget)

        dir_row = QHBoxLayout()
        self.download_dir = QLineEdit(str(Path.home() / "Downloads" / "VideoBridge"))
        btn = QPushButton("选择目录")
        btn.setProperty("secondary", True)
        btn.clicked.connect(self._pick_download_dir)
        btn_open = QPushButton("打开")
        btn_open.setProperty("secondary", True)
        btn_open.clicked.connect(lambda: self._open_dir(self.download_dir.text()))
        dir_row.addWidget(self.download_dir, 1)
        dir_row.addWidget(btn)
        dir_row.addWidget(btn_open)
        form.addRow("输出目录", dir_row)

        self.btn_download = QPushButton("开始下载")
        self.btn_download.clicked.connect(self._run_download)
        form.addRow("", self.btn_download)
        return page

    def _pick_download_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择下载目录")
        if d:
            self.download_dir.setText(d)

    def _run_douyin_login(self):
        self.btn_douyin_login.setEnabled(False)
        self._log("打开抖音扫码登录窗口，请使用手机抖音扫码...")
        thread = threading.Thread(target=self._task_douyin_login, daemon=True)
        thread.start()

    def _task_douyin_login(self):
        try:
            path = douyin_login()
            self.douyin_login_done.emit(path)
        except Exception as exc:
            self._log(f"[抖音登录失败] {exc}")
            self.task_finished.emit(self.btn_douyin_login)

    def _on_douyin_login_done(self, path: str):
        self._douyin_cookie_path = path
        self._log("抖音登录成功，Cookie 已保存")
        self.btn_douyin_login.setText("抖音 Cookie 已就绪")
        self.btn_douyin_login.setEnabled(True)

    def _refresh_download_url(self):
        text = self.download_url.toPlainText().strip()
        url = extract_video_url(text) or text
        if url and url.startswith(("http://", "https://")):
            self.download_url_clean.setText(url)
        else:
            self.download_url_clean.clear()
        self._update_douyin_login_visibility(url)

    def _update_douyin_login_visibility(self, url: str | None):
        is_douyin = bool(url and detect_platform(url) == "douyin")
        self.douyin_login_widget.setVisible(is_douyin)

    def _run_download(self):
        raw_text = self.download_url.toPlainText().strip()
        url = self.download_url_clean.text().strip() or extract_video_url(raw_text) or raw_text
        output_dir = self.download_dir.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请先粘贴视频链接")
            return
        if not output_dir:
            QMessageBox.warning(self, "提示", "请选择输出目录")
            return
        platform = self.download_platform.currentData() or "auto"
        cookies_file = self._douyin_cookie_path or ""
        self._start(
            self.btn_download,
            self._task_download,
            url,
            output_dir,
            platform,
            cookies_file,
            "",
        )

    def _task_download(
        self,
        button,
        url: str,
        output_dir: str,
        platform: str,
        cookies_file: str,
        browser: str,
    ):
        try:
            self._log(f"开始下载: {url}")
            resolved_platform = platform if platform != "auto" else detect_platform(url)
            if resolved_platform == "douyin" and not cookies_file and not browser:
                self._log("检测到抖音视频链接，自动获取抖音 Fresh Cookie...")
                try:
                    cookies_file = fetch_douyin_cookies()
                    self._douyin_cookie_path = cookies_file
                    self._log("抖音 Cookie 获取完成")
                except Exception as exc:
                    self._log(f"[自动获取 Cookie 失败] {exc}")
                    raise RuntimeError("自动获取抖音 Cookie 失败，请手动选择 Cookie 文件或浏览器 Cookie") from exc
            bins = BinaryPaths.detect()
            os.makedirs(output_dir, exist_ok=True)
            result = download_video(
                url,
                output_dir,
                platform=None if platform == "auto" else platform,
                cookies_file=cookies_file or None,
                cookies_from_browser=browser or None,
                binaries=bins,
                on_line=self._log,
            )
            self._log(f"下载完成: {result.filepath}")
        except Exception as exc:
            self._log(f"[下载失败] {exc}")
        finally:
            self.task_finished.emit(button)

    # ---------- 字幕模块 ----------
    def _build_subtitle_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(4, 8, 4, 4)
        group = QGroupBox("字幕设置")
        form = QFormLayout(group)
        form.setContentsMargins(20, 30, 20, 20)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        outer.addWidget(group)
        outer.addStretch(1)

        file_row = QHBoxLayout()
        self.subtitle_file = QLineEdit()
        self.subtitle_file.setPlaceholderText("选择本地视频文件")
        btn_file = QPushButton("选择视频")
        btn_file.setProperty("secondary", True)
        btn_file.clicked.connect(self._pick_subtitle_file)
        file_row.addWidget(self.subtitle_file, 1)
        file_row.addWidget(btn_file)
        form.addRow("视频文件", file_row)

        model_row = QHBoxLayout()
        self.subtitle_model = QLineEdit()
        self.subtitle_model.setPlaceholderText("选择 whisper.cpp 模型 .bin")
        btn_model = QPushButton("选择模型")
        btn_model.setProperty("secondary", True)
        btn_model.clicked.connect(self._pick_subtitle_model)
        model_row.addWidget(self.subtitle_model, 1)
        model_row.addWidget(btn_model)
        self.btn_download_model = QPushButton("下载默认模型")
        self.btn_download_model.clicked.connect(self._ask_download_model)
        model_row.addWidget(self.btn_download_model)
        form.addRow("Whisper 模型", model_row)

        self.subtitle_lang = QComboBox()
        languages = [
            ("自动检测", "auto"),
            ("中文", "zh"),
            ("English", "en"),
            ("日本語", "ja"),
            ("한국어", "ko"),
            ("Français", "fr"),
            ("Español", "es"),
            ("Русский", "ru"),
            ("Deutsch", "de"),
            ("Português", "pt"),
        ]
        for label, code in languages:
            self.subtitle_lang.addItem(label, code)
        self.subtitle_lang.setCurrentIndex(0)
        form.addRow("语言", self.subtitle_lang)

        self.subtitle_burn = QCheckBox("生成字幕并烧录到视频")
        self.subtitle_burn.setChecked(True)
        form.addRow("", self.subtitle_burn)

        self.btn_subtitle = QPushButton("生成字幕")
        self.btn_subtitle.clicked.connect(self._run_subtitle)
        form.addRow("", self.btn_subtitle)
        return page

    def _pick_subtitle_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "选择本地视频",
            str(Path.home()),
            "Video (*.mp4 *.mov *.mkv *.webm *.flv *.avi)",
        )
        if f:
            self.subtitle_file.setText(f)

    def _pick_subtitle_model(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 whisper.cpp 模型", str(Path.cwd()), "Model (*.bin)")
        if f:
            self.subtitle_model.setText(f)

    def _default_model_path(self) -> str:
        return str(Path.cwd() / "models" / "ggml-small.bin")

    def _init_model_state(self):
        default = self._default_model_path()
        if os.path.isfile(default):
            if not self.subtitle_model.text().strip():
                self.subtitle_model.setText(default)
            self.btn_download_model.setText("模型已就绪")
            self.btn_download_model.setEnabled(False)

    def _ask_download_model(self):
        dest = self.subtitle_model.text().strip() or self._default_model_path()
        if os.path.isfile(dest):
            self._log(f"模型已存在: {dest}")
            return
        ret = QMessageBox.question(
            self,
            "下载字幕模型",
            "需要下载 whisper.cpp 默认模型 ggml-small.bin（约 500MB），是否现在下载？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self._start_model_download(dest)

    def _start_model_download(self, dest: str):
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.btn_subtitle.setEnabled(False)
        self.btn_download_model.setEnabled(False)
        thread = threading.Thread(target=self._task_model_download, args=(dest,), daemon=True)
        thread.start()

    def _task_model_download(self, dest: str):
        try:
            self._log(f"开始下载模型: {dest}")
            download_model(
                dest,
                model_name=os.path.basename(dest),
                on_progress=lambda done, total: self.model_progress.emit(done, total),
                on_status=self._log,
            )
            self.model_ready.emit(dest)
        except Exception as exc:
            self._log(f"[模型下载失败] {exc}")
        finally:
            self.model_finished.emit()

    def _on_model_progress(self, done: int, total: int | None):
        if total:
            self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(100, int(done * 100 / total))))
        else:
            self.progress.setRange(0, 0)

    def _on_model_ready(self, dest: str):
        self.subtitle_model.setText(dest)
        self._log("模型下载完成，可以开始生成字幕")

    def _on_model_finished(self):
        self.progress.hide()
        self.btn_subtitle.setEnabled(True)
        self.btn_download_model.setEnabled(True)
        if os.path.isfile(self.subtitle_model.text().strip()):
            self.btn_download_model.setText("模型已就绪")
            self.btn_download_model.setEnabled(False)

    def _run_subtitle(self):
        video = self.subtitle_file.text().strip()
        model = self.subtitle_model.text().strip() or self._default_model_path()
        if not video:
            QMessageBox.warning(self, "提示", "请选择本地视频文件")
            return
        if not os.path.isfile(video):
            QMessageBox.warning(self, "提示", "视频文件不存在")
            return
        if not os.path.isfile(model):
            ret = QMessageBox.question(
                self,
                "需要下载模型",
                "字幕模型不存在，是否现在下载默认模型 ggml-small.bin（约 500MB）？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret == QMessageBox.Yes:
                self.subtitle_model.setText(model)
                self._start_model_download(model)
            return
        self.subtitle_model.setText(model)
        burn = self.subtitle_burn.isChecked()
        self._start(
            self.btn_subtitle,
            self._task_subtitle,
            video,
            model,
            self.subtitle_lang.currentData() or "auto",
            burn,
        )

    def _task_subtitle(self, button, video: str, model: str, language: str, burn: bool):
        try:
            self._log(f"开始生成字幕: {video}")
            bins = BinaryPaths.detect()
            output_dir = os.path.dirname(os.path.abspath(video))
            srt = generate_srt(
                video,
                model_path=model,
                output_dir=output_dir,
                language=language,
                binaries=bins,
                on_line=self._log,
            )
            self._log(f"字幕完成: {srt}")
            if burn:
                stem = os.path.splitext(os.path.basename(video))[0]
                burned = os.path.join(output_dir, f"{stem}.subbed.mp4")
                self._log("开始烧录字幕到视频…")
                burn_subtitles(
                    video,
                    srt,
                    burned,
                    ffmpeg_bin=bins.ffmpeg,
                    on_line=self._log,
                )
                self._log(f"烧录完成: {burned}")
        except Exception as exc:
            self._log(f"[字幕失败] {exc}")
        finally:
            self.task_finished.emit(button)

    # ---------- 去重模块 ----------
    def _build_dedup_tab(self) -> QWidget:
        page = QWidget()
        root_layout = QVBoxLayout(page)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(4, 8, 4, 4)
        group = QGroupBox("去重 / 二创")
        form = QFormLayout(group)
        form.setContentsMargins(20, 30, 20, 20)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        outer.addWidget(group)
        outer.addStretch(1)

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

        file_row = QHBoxLayout()
        self.dedup_file = QLineEdit()
        self.dedup_file.setPlaceholderText("选择本地视频文件")
        btn_file = QPushButton("选择视频")
        btn_file.setProperty("secondary", True)
        btn_file.clicked.connect(self._pick_dedup_file)
        file_row.addWidget(self.dedup_file, 1)
        file_row.addWidget(btn_file)
        form.addRow("视频文件", file_row)

        dir_row = QHBoxLayout()
        self.dedup_dir = QLineEdit(str(Path.home() / "Downloads" / "VideoBridge"))
        btn_dir = QPushButton("选择目录")
        btn_dir.setProperty("secondary", True)
        btn_dir.clicked.connect(self._pick_dedup_dir)
        btn_open_dir = QPushButton("打开")
        btn_open_dir.setProperty("secondary", True)
        btn_open_dir.clicked.connect(lambda: self._open_dir(self.dedup_dir.text()))
        dir_row.addWidget(self.dedup_dir, 1)
        dir_row.addWidget(btn_dir)
        dir_row.addWidget(btn_open_dir)
        form.addRow("输出目录", dir_row)

        mix_row = QHBoxLayout()
        self.dedup_mix_file = QLineEdit()
        self.dedup_mix_file.setPlaceholderText("可选：选择另一段素材，启用抽帧混合")
        btn_mix = QPushButton("选择素材")
        btn_mix.setProperty("secondary", True)
        btn_mix.clicked.connect(self._pick_dedup_mix_file)
        mix_row.addWidget(self.dedup_mix_file, 1)
        mix_row.addWidget(btn_mix)
        form.addRow("抽帧混合素材", mix_row)

        bgm_row = QHBoxLayout()
        self.dedup_bgm_file = QLineEdit()
        self.dedup_bgm_file.setPlaceholderText("可选：选择背景音乐，叠加到视频")
        btn_bgm = QPushButton("选择 BGM")
        btn_bgm.setProperty("secondary", True)
        btn_bgm.clicked.connect(self._pick_dedup_bgm_file)
        bgm_row.addWidget(self.dedup_bgm_file, 1)
        bgm_row.addWidget(btn_bgm)
        form.addRow("背景音乐", bgm_row)

        pip_row = QHBoxLayout()
        self.dedup_pip_file = QLineEdit()
        self.dedup_pip_file.setPlaceholderText("可选：选择另一段视频，作为角落画中画")
        btn_pip = QPushButton("选择画中画")
        btn_pip.setProperty("secondary", True)
        btn_pip.clicked.connect(self._pick_dedup_pip_file)
        pip_row.addWidget(self.dedup_pip_file, 1)
        pip_row.addWidget(btn_pip)
        form.addRow("画中画素材", pip_row)

        seg_row = QHBoxLayout()
        self.dedup_segments_enable = QCheckBox("随机片段重排")
        self.dedup_segment_count = QSpinBox()
        self.dedup_segment_count.setRange(2, 8)
        self.dedup_segment_count.setValue(3)
        seg_row.addWidget(self.dedup_segments_enable)
        seg_row.addWidget(QLabel("段数"))
        seg_row.addWidget(self.dedup_segment_count)
        seg_row.addStretch(1)
        form.addRow("片段处理", seg_row)

        self.dedup_strength = QComboBox()
        self.dedup_strength.addItems(["轻度", "中度", "重度"])
        self.dedup_strength.setCurrentText("中度")
        form.addRow("去重强度", self.dedup_strength)

        self.dedup_mirror = QCheckBox("水平镜像")
        self.dedup_mirror.setChecked(True)
        form.addRow("处理选项", self.dedup_mirror)

        sat_row = QHBoxLayout()
        self.dedup_saturation = QDoubleSpinBox()
        self.dedup_saturation.setRange(0.5, 2.0)
        self.dedup_saturation.setSingleStep(0.05)
        self.dedup_saturation.setValue(1.05)
        sat_row.addWidget(self.dedup_saturation, 1)
        form.addRow("饱和度（微调）", sat_row)

        contrast_row = QHBoxLayout()
        self.dedup_contrast = QDoubleSpinBox()
        self.dedup_contrast.setRange(0.5, 2.0)
        self.dedup_contrast.setSingleStep(0.05)
        self.dedup_contrast.setValue(1.03)
        contrast_row.addWidget(self.dedup_contrast, 1)
        form.addRow("对比度（微调）", contrast_row)

        self.dedup_random = QCheckBox("随机参数（每次输出不同）")
        self.dedup_random.setChecked(True)
        form.addRow("", self.dedup_random)

        self.btn_dedup = QPushButton("开始去重")
        self.btn_dedup.clicked.connect(self._run_dedup)
        form.addRow("", self.btn_dedup)
        return page

    def _pick_dedup_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "选择本地视频",
            str(Path.home()),
            "Video (*.mp4 *.mov *.mkv *.webm *.flv *.avi)",
        )
        if f:
            self.dedup_file.setText(f)

    def _pick_dedup_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.dedup_dir.setText(d)

    def _pick_dedup_mix_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "选择抽帧混合素材视频",
            str(Path.home()),
            "Video (*.mp4 *.mov *.mkv *.webm *.flv *.avi)",
        )
        if f:
            self.dedup_mix_file.setText(f)

    def _pick_dedup_bgm_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "选择背景音乐",
            str(Path.home()),
            "Audio (*.mp3 *.wav *.m4a *.aac *.flac)",
        )
        if f:
            self.dedup_bgm_file.setText(f)

    def _pick_dedup_pip_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "选择画中画素材",
            str(Path.home()),
            "Video (*.mp4 *.mov *.mkv *.webm *.flv *.avi)",
        )
        if f:
            self.dedup_pip_file.setText(f)

    def _run_dedup(self):
        video = self.dedup_file.text().strip()
        output_dir = self.dedup_dir.text().strip()
        if not video:
            QMessageBox.warning(self, "提示", "请选择本地视频文件")
            return
        if not os.path.isfile(video):
            QMessageBox.warning(self, "提示", "视频文件不存在")
            return
        if not output_dir:
            QMessageBox.warning(self, "提示", "请选择输出目录")
            return
        opts = options_from_strength(
            self.dedup_strength.currentText(),
            mirror=self.dedup_mirror.isChecked(),
            saturation=self.dedup_saturation.value(),
            contrast=self.dedup_contrast.value(),
            randomize=self.dedup_random.isChecked(),
        )
        mix_file = self.dedup_mix_file.text().strip()
        bgm_file = self.dedup_bgm_file.text().strip()
        pip_file = self.dedup_pip_file.text().strip()
        segments_enabled = self.dedup_segments_enable.isChecked()
        segment_count = self.dedup_segment_count.value()
        if mix_file and not os.path.isfile(mix_file):
            QMessageBox.warning(self, "提示", "抽帧混合素材文件不存在")
            return
        if bgm_file and not os.path.isfile(bgm_file):
            QMessageBox.warning(self, "提示", "背景音乐文件不存在")
            return
        if pip_file and not os.path.isfile(pip_file):
            QMessageBox.warning(self, "提示", "画中画素材文件不存在")
            return
        self._start(
            self.btn_dedup,
            self._task_dedup,
            video,
            output_dir,
            opts,
            mix_file,
            bgm_file,
            pip_file,
            segments_enabled,
            segment_count,
        )

    def _task_dedup(
        self,
        button,
        video: str,
        output_dir: str,
        opts: DedupOptions,
        mix_file: str,
        bgm_file: str,
        pip_file: str,
        segments_enabled: bool,
        segment_count: int,
    ):
        try:
            self._log(f"开始去重/二创: {video}")
            bins = BinaryPaths.detect()
            stem = os.path.splitext(os.path.basename(video))[0]
            current = video
            temp_files = []
            advanced_used = bool(mix_file or pip_file or bgm_file or segments_enabled)

            def make_temp(name: str) -> str:
                path = os.path.join(output_dir, f".{stem}.{name}_tmp.mp4")
                temp_files.append(path)
                return path

            # 1. 主结构处理：抽帧混合优先；否则片段重排；否则滤镜参数去重
            if mix_file:
                mixed = make_temp("mix")
                self._log("使用抽帧混合模式（素材 B 帧插入内容 A）…")
                dedup_frame_mix(video, mix_file, mixed, binaries=bins, on_line=self._log)
                current = mixed
                self._log("抽帧混合完成")

            if segments_enabled:
                seg = make_temp("seg")
                self._log(f"使用随机片段重排（{segment_count} 段）…")
                dedup_random_segments(
                    current,
                    seg,
                    segment_count=segment_count,
                    shuffle=True,
                    binaries=bins,
                    on_line=self._log,
                )
                current = seg
                self._log("片段重排完成")

            if not mix_file and not segments_enabled:
                if advanced_used:
                    normal = make_temp("normal")
                else:
                    normal = os.path.join(output_dir, f"{stem}.dedup.mp4")
                self._log("使用滤镜参数去重模式…")
                dedup_video(current, normal, opts, binaries=bins, on_line=self._log)
                current = normal

            # 2. 画中画叠加
            if pip_file:
                pip = make_temp("pip")
                self._log("叠加画中画素材…")
                dedup_pip(current, pip_file, pip, binaries=bins, on_line=self._log)
                current = pip
                self._log("画中画完成")

            # 3. BGM 或收尾输出
            if bgm_file:
                final = os.path.join(output_dir, f"{stem}.final.mp4")
                self._log("叠加背景音乐…")
                add_background_music(current, bgm_file, final, binaries=bins, on_line=self._log)
                current = final
                self._log(f"去重完成: {final}")
            elif advanced_used:
                final = os.path.join(output_dir, f"{stem}.final.mp4")
                os.replace(current, final)
                current = final
                self._log(f"去重完成: {final}")
            else:
                self._log(f"去重完成: {current}")

            # 4. 清理临时文件
            for tmp in temp_files:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
        except Exception as exc:
            self._log(f"[去重失败] {exc}")
        finally:
            self.task_finished.emit(button)

    # ---------- 配音模块 ----------
    def _build_dub_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(4, 8, 4, 4)
        group = QGroupBox("配音")
        form = QFormLayout(group)
        form.setContentsMargins(20, 30, 20, 20)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        outer.addWidget(group)
        outer.addStretch(1)

        video_row = QHBoxLayout()
        self.dub_video_file = QLineEdit()
        self.dub_video_file.setPlaceholderText("可选：选择视频，将原声替换为配音")
        btn_video = QPushButton("选择视频")
        btn_video.setProperty("secondary", True)
        btn_video.clicked.connect(self._pick_dub_video_file)
        video_row.addWidget(self.dub_video_file, 1)
        video_row.addWidget(btn_video)
        form.addRow("替换视频原声", video_row)

        self.dub_text = QTextEdit()
        self.dub_text.setPlaceholderText("输入需要配音的文字，例如字幕内容、旁白或解说词…")
        self.dub_text.setMinimumHeight(120)
        form.addRow("配音文本", self.dub_text)

        self.dub_voice = QComboBox()
        for label, code in voice_options():
            self.dub_voice.addItem(label, code)
        self.dub_voice.setCurrentIndex(0)
        form.addRow("配音音色", self.dub_voice)

        self.dub_rate = QComboBox()
        self.dub_rate.addItems(RATES)
        self.dub_rate.setCurrentText("+0%")
        form.addRow("语速", self.dub_rate)

        out_row = QHBoxLayout()
        self.dub_output = QLineEdit(str(Path.home() / "Downloads" / "VideoBridge" / "dub.mp3"))
        btn_save = QPushButton("选择保存位置")
        btn_save.setProperty("secondary", True)
        btn_save.clicked.connect(self._pick_dub_output)
        out_row.addWidget(self.dub_output, 1)
        out_row.addWidget(btn_save)
        form.addRow("输出音频", out_row)

        self.btn_dub = QPushButton("生成配音")
        self.btn_dub.clicked.connect(self._run_dub)
        form.addRow("", self.btn_dub)
        return page

    def _pick_dub_video_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "选择要替换原声的视频",
            str(Path.home()),
            "Video (*.mp4 *.mov *.mkv *.webm *.flv *.avi)",
        )
        if f:
            self.dub_video_file.setText(f)

    def _pick_dub_output(self):
        f, _ = QFileDialog.getSaveFileName(
            self,
            "保存配音",
            self.dub_output.text().strip() or str(Path.home() / "Downloads" / "VideoBridge" / "dub.mp3"),
            "Audio (*.mp3)",
        )
        if f:
            self.dub_output.setText(f)

    def _run_dub(self):
        text = self.dub_text.toPlainText().strip()
        output = self.dub_output.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入需要配音的文字")
            return
        if not output:
            QMessageBox.warning(self, "提示", "请选择音频保存位置")
            return
        voice = self.dub_voice.currentData() or "zh-CN-XiaoxiaoNeural"
        rate = self.dub_rate.currentText() or "+0%"
        video = self.dub_video_file.text().strip()
        if video and not os.path.isfile(video):
            QMessageBox.warning(self, "提示", "视频文件不存在")
            return
        self._start(self.btn_dub, self._task_dub, text, output, voice, rate, video)

    def _task_dub(self, button, text: str, output: str, voice: str, rate: str, video: str):
        tmp_audio = None
        try:
            self._log(f"开始生成配音: {voice} / {rate}")
            if video:
                tmp_audio = output + ".dub_tmp.mp3"
                text_to_speech(text, tmp_audio, voice=voice, rate=rate, on_status=self._log)
                stem = os.path.splitext(os.path.basename(video))[0]
                out_video = os.path.join(os.path.dirname(os.path.abspath(video)), f"{stem}.dubbed.mp4")
                replace_video_audio(video, tmp_audio, out_video, on_status=self._log)
                self._log(f"配音视频完成: {out_video}")
            else:
                text_to_speech(text, output, voice=voice, rate=rate, on_status=self._log)
                self._log(f"配音完成: {output}")
        except Exception as exc:
            self._log(f"[配音失败] {exc}")
        finally:
            if tmp_audio and os.path.exists(tmp_audio):
                try:
                    os.remove(tmp_audio)
                except OSError:
                    pass
            self.task_finished.emit(button)

    # ---------- 通用 ----------
    def _open_dir(self, path: str):
        path = (path or "").strip()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "提示", "目录不存在或尚未创建")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _start(self, button, task, *args):
        button.setEnabled(False)
        thread = threading.Thread(target=task, args=(button, *args), daemon=True)
        thread.start()
        self.progress.setVisible(True)

    def _on_task_finished(self):
        self.progress.hide()

    def _log(self, msg: str):
        self.append_log.emit(msg)

    def _append_line(self, msg: str):
        self.log_view.appendPlainText(msg)

