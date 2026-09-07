from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow
    from app.ui.theme import app_stylesheet

    app = QApplication(sys.argv)
    app.setApplicationName("VideoBridge")
    app.setStyleSheet(app_stylesheet())
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
