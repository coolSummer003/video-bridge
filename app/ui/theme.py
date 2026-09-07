"""VideoBridge 全局 UI 主题样式。"""
from __future__ import annotations

PRIMARY = "#4F6EF7"
PRIMARY_HOVER = "#3D5CE5"
PRIMARY_PRESSED = "#324BC2"
BG = "#F4F6FB"
CARD_BG = "#FFFFFF"
TEXT = "#1F2937"
MUTED = "#6B7280"
BORDER = "#D8DFEA"


def app_stylesheet() -> str:
    return f"""
    * {{
        font-family: "PingFang SC", "Helvetica Neue", "Microsoft YaHei", sans-serif;
        color: {TEXT};
        font-size: 13px;
    }}

    QMainWindow, QWidget {{
        background-color: {BG};
    }}

    QTabWidget::pane {{
        border: none;
        background: transparent;
    }}

    QTabBar::tab {{
        background: transparent;
        color: {MUTED};
        padding: 10px 28px;
        margin-right: 4px;
        border: none;
        border-bottom: 3px solid transparent;
        font-size: 15px;
        font-weight: 500;
    }}

    QTabBar::tab:selected {{
        color: {PRIMARY};
        border-bottom: 3px solid {PRIMARY};
        font-weight: 600;
    }}

    QTabBar::tab:hover:!selected {{
        color: {TEXT};
    }}

    QLineEdit, QPlainTextEdit, QDoubleSpinBox {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 8px 10px;
        selection-background-color: {PRIMARY};
        selection-color: white;
    }}

    QLineEdit:focus, QPlainTextEdit:focus, QDoubleSpinBox:focus {{
        border: 1px solid {PRIMARY};
        background: white;
    }}

    QPushButton {{
        background-color: {PRIMARY};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 8px 18px;
        font-weight: 500;
    }}

    QPushButton:hover {{
        background-color: {PRIMARY_HOVER};
    }}

    QPushButton:pressed {{
        background-color: {PRIMARY_PRESSED};
    }}

    QPushButton:disabled {{
        background-color: #C7CEE0;
        color: #F0F2F8;
    }}

    QPushButton[secondary="true"] {{
        background-color: white;
        color: {PRIMARY};
        border: 1px solid {PRIMARY};
    }}

    QPushButton[secondary="true"]:hover {{
        background-color: #EEF2FF;
    }}

    QPushButton[secondary="true"]:disabled {{
        background-color: #F3F4F6;
        color: #A6AEBD;
        border-color: #D8DFEA;
    }}

    QProgressBar {{
        background: #E5EAF3;
        border: none;
        border-radius: 6px;
        height: 12px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {PRIMARY};
        border-radius: 6px;
    }}

    QCheckBox {{
        spacing: 8px;
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 1px solid {BORDER};
        background: white;
    }}

    QCheckBox::indicator:checked {{
        background-color: {PRIMARY};
        border-color: {PRIMARY};
    }}

    QLabel {{
        color: {TEXT};
    }}

    QLabel#appTitle {{
        font-size: 24px;
        font-weight: 700;
        color: #111827;
        letter-spacing: 0.5px;
    }}

    QLabel#appSubtitle {{
        font-size: 13px;
        color: {MUTED};
        margin-bottom: 6px;
    }}

    QGroupBox {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 14px;
        margin-top: 14px;
        font-weight: 600;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 18px;
        padding: 0 8px;
        color: {PRIMARY};
        font-size: 14px;
        font-weight: 600;
    }}

    QComboBox, QSpinBox {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 6px 10px;
        min-height: 24px;
    }}

    QComboBox:focus, QSpinBox:focus {{
        border: 1px solid {PRIMARY};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox QAbstractItemView {{
        background: white;
        border: 1px solid {BORDER};
        border-radius: 8px;
        selection-background-color: #EEF2FF;
        selection-color: {TEXT};
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: #C7CEE0;
        border-radius: 4px;
        min-height: 24px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {PRIMARY};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
    }}

    QScrollBar::handle:horizontal {{
        background: #C7CEE0;
        border-radius: 4px;
        min-width: 24px;
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    """
