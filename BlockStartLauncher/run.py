import os
import sys

if __name__ == "__main__":
    from core.elevation import ensure_admin

    if not ensure_admin():
        sys.exit(0)

import traceback

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from core.icon_factory import create_app_icon
from ui.main_window import MainWindow

import config


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(f"BlockStart Launcher V{config.LAUNCHER_VERSION} by MC_Family")
    app.setWindowIcon(create_app_icon())
    window = MainWindow()
    window.show()
    if os.environ.get("BSL_SMOKE_TEST") == "1":
        QTimer.singleShot(1200, window.close)
        QTimer.singleShot(2000, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "BlockStart Launcher 错误", tb)
        sys.exit(1)
