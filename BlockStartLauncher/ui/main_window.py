import os
import sys
import time

from PySide6.QtCore import QByteArray, QSize, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import config
from core import account_manager, launcher_core, worker
from core.icon_factory import create_app_icon, create_nav_icon, create_pixmap
from core.music_player import MusicPlayer
from core.settings_store import SettingsStore
from ui.account_page import AccountPage
from ui.animations import fade_in
from ui.dashboard_page import DashboardPage
from ui.instance_page import InstancePage
from ui.mod_browser import ModBrowserPage
from ui.modpack_page import ModpackPage
from ui.repair_page import RepairPage
from ui.resource_page import ResourcePage
from ui.settings_page import SettingsPage
from ui.theme import get_stylesheet
from ui.toast import Toast


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = SettingsStore()
        self._pages = []
        self._workers = []
        self._music = None
        self._toast = None
        self._restored_once = False
        self._update_checked = False
        self._ui_ready = False
        self._prepare_game_dir()
        self.setWindowTitle(f"BlockStart Launcher V{config.LAUNCHER_VERSION} by MC_Family")
        self.resize(1100, 720)
        self.setMinimumSize(960, 620)
        self.setWindowIcon(create_app_icon())
        self._build_ui()
        self._connect_pages()
        self.apply_theme(self.settings.get("theme") or "dark")
        self._restore_window()
        self.apply_background()
        self.reload_instances(self.settings.get("last_instance") or "")
        self.dashboard.refresh_account()
        self.apply_music()
        self.log("BlockStart Launcher V" + config.LAUNCHER_VERSION + " 已启动")
        self._ui_ready = True

    def _prepare_game_dir(self):
        game_dir = str(self.settings.get("game_dir") or "").strip()
        if game_dir and not os.path.isdir(game_dir):
            game_dir = ""
            self.settings.set("game_dir", "")
        if not game_dir and getattr(sys, "frozen", False):
            legacy = config.legacy_minecraft_dir()
            new_dir = os.path.join(config.data_dir(), config.MINECRAFT_DIR)
            if os.path.isdir(legacy) and not os.path.isdir(new_dir):
                game_dir = legacy
        if not game_dir:
            game_dir = os.path.join(config.data_dir(), config.MINECRAFT_DIR)
        config.set_game_dir(game_dir)
        self.settings.set("game_dir", game_dir)
        self._remember_game_dir(game_dir)

    def _remember_game_dir(self, path):
        path = os.path.abspath(str(path or "").strip())
        if not path:
            return
        directories = self.settings.get("game_dirs")
        if not isinstance(directories, list):
            directories = []
        normalized = {os.path.normcase(os.path.abspath(str(item))) for item in directories if item}
        if os.path.normcase(path) not in normalized:
            directories.append(path)
        self.settings.set("game_dirs", directories[-8:])

    def change_game_dir(self, path):
        path = os.path.abspath(str(path or "").strip())
        if not path:
            return
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as exc:
            self.log("无法使用该游戏目录：" + str(exc))
            return
        config.set_game_dir(path)
        self.settings.set("game_dir", path)
        self._remember_game_dir(path)
        self.settings.save()
        self.reload_instances("")
        self.log("游戏目录已切换到：" + path)
        self.toast("游戏目录已切换", "success")

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("Root")
        self._root = central
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(186)
        sidebar.setMaximumWidth(210)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 14)
        sidebar_layout.setSpacing(6)

        brand_row = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(create_pixmap(42))
        brand_row.addWidget(logo)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        app_name = QLabel("BlockStart")
        app_name.setObjectName("AppName")
        brand_text.addWidget(app_name)
        version = QLabel("启动器 V" + config.LAUNCHER_VERSION)
        version.setObjectName("Muted")
        brand_text.addWidget(version)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addSpacing(14)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []
        nav_items = [
            ("主页", "home"),
            ("游戏实例", "instance"),
            ("账户", "account"),
            ("模组", "mod"),
            ("整合包", "modpack"),
            ("资源", "resource"),
            ("修复工具", "repair"),
            ("设置", "settings"),
        ]
        for index, (title, icon_name) in enumerate(nav_items):
            button = QPushButton(title)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setIcon(create_nav_icon(icon_name))
            button.setIconSize(QSize(24, 24))
            button.clicked.connect(lambda _checked=False, i=index: self.switch_tab(i))
            self.nav_group.addButton(button, index)
            sidebar_layout.addWidget(button)
            self.nav_buttons.append(button)
        sidebar_layout.addStretch(1)
        footer = QLabel("作者 MC_Family\n简单、可靠的启动器")
        footer.setObjectName("SidebarFooter")
        sidebar_layout.addWidget(footer)
        outer.addWidget(sidebar)

        right = QWidget()
        layout = QVBoxLayout(right)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self.tabs = QTabWidget()
        self.tabs.tabBar().setVisible(False)
        self.tabs.currentChanged.connect(self._sync_nav)
        self.dashboard = DashboardPage(self.settings, self)
        self.instance_page = InstancePage(self.settings, self)
        self.account_page = AccountPage(self.settings, self)
        self.mod_browser = ModBrowserPage(self.settings, self)
        self.modpack_page = ModpackPage(self.settings, self)
        self.resource_page = ResourcePage(self.settings, self)
        self.repair_page = RepairPage(self.settings, self)
        self.settings_page = SettingsPage(self.settings, self)
        self._pages = [
            self.dashboard,
            self.instance_page,
            self.account_page,
            self.mod_browser,
            self.modpack_page,
            self.resource_page,
            self.repair_page,
            self.settings_page,
        ]
        for page, title in zip(
            self._pages, ["主页", "游戏实例", "账户", "模组", "整合包", "资源", "修复工具", "设置"]
        ):
            if page is self.settings_page:
                self.tabs.addTab(page, title)
                continue
            container = QScrollArea()
            container.setWidgetResizable(True)
            container.setFrameShape(QFrame.NoFrame)
            container.setWidget(page)
            self.tabs.addTab(container, title)
        if self.nav_buttons:
            self.nav_buttons[0].setChecked(True)
        layout.addWidget(self.tabs, 1)

        log_row = QHBoxLayout()
        log_row.addStretch(1)
        self.log_toggle_btn = QPushButton("运行日志")
        self.log_toggle_btn.clicked.connect(self.toggle_log)
        log_row.addWidget(self.log_toggle_btn)
        layout.addLayout(log_row)
        self.log_view = QTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(140)
        self.log_view.setVisible(False)
        layout.addWidget(self.log_view)
        outer.addWidget(right, 1)
        self.setCentralWidget(central)

    def _sync_nav(self, index):
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)
        if getattr(self, "_ui_ready", False):
            self.settings.set("last_page_index", index)
            self.settings.save()

    def _connect_pages(self):
        self.instance_page.instance_changed.connect(self.on_instance_changed)
        self.account_page.account_changed.connect(self._on_account_changed)

    def current_instance_name(self):
        name = self.settings.get("last_instance") or ""
        if name and launcher_core.get_instance(name):
            return name
        instances = launcher_core.list_instances()
        return instances[0]["name"] if instances else ""

    def current_account(self):
        accounts = account_manager.list_accounts()
        target = self.settings.get("last_account_uuid") or ""
        for account in accounts:
            if account.get("id") == target:
                return account
        offline = next((account for account in accounts if account.get("type") != "msa"), None)
        if offline:
            return offline
        return accounts[0] if accounts else None

    def reload_instances(self, select=None):
        instances = launcher_core.list_instances()
        names = [instance["name"] for instance in instances]
        if select not in names:
            saved = self.settings.get("last_instance") or ""
            select = saved if saved in names else (names[0] if names else "")
        self.instance_page.reload(select)
        actual = self.instance_page.current_name()
        if actual:
            select = actual
        self.on_instance_changed(select)
        self.repair_page.reload_versions()

    def on_instance_changed(self, name):
        instance = launcher_core.get_instance(name) if name else None
        if name and not instance:
            name = ""
        self.settings.set("last_instance", name)
        self.settings.set("last_version_id", instance.get("version_id") if instance else "")
        self.settings.save()
        self.dashboard.on_instance_changed(name)
        self.mod_browser.on_instance_changed(name)
        self.resource_page.on_instance_changed(name)

    def select_instance(self, name):
        if not launcher_core.get_instance(name):
            return
        self.instance_page.reload(name)
        self.on_instance_changed(name)

    def _on_account_changed(self, account_id):
        self.settings.set("last_account_uuid", account_id or "")
        self.settings.save()
        self.dashboard.refresh_account()
        if getattr(self, "_ui_ready", False):
            self.toast("账户已切换", "success")

    def attach_worker(self, task):
        if task is None:
            return
        self._workers.append(task)
        task.finished_error.connect(lambda message: self.log("错误：" + str(message)))
        task.finished.connect(lambda: self._release_worker(task))

    def _release_worker(self, task):
        try:
            if task in self._workers:
                self._workers.remove(task)
        except Exception:
            pass

    def log(self, text):
        try:
            view = getattr(self, "log_view", None)
            if view is None:
                return
            stamp = time.strftime("%H:%M:%S")
            view.append(f"[{stamp}] {text}")
        except Exception:
            pass

    def toggle_log(self):
        visible = not self.log_view.isVisible()
        self.log_view.setVisible(visible)
        self.log_toggle_btn.setText("收起日志" if visible else "运行日志")

    def switch_tab(self, index):
        if 0 <= index < self.tabs.count():
            changed = self.tabs.currentIndex() != index
            self.tabs.setCurrentIndex(index)
            self._sync_nav(index)
            if changed and self.settings.get("animations", True):
                page = self.tabs.widget(index)
                QTimer.singleShot(0, lambda widget=page: fade_in(widget, 170))

    def toast(self, text, kind="info", duration=2600):
        if self._toast is None:
            self._toast = Toast(self)
        self._toast.show_message(text, kind, duration)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._toast is not None and self._toast.isVisible():
            self._toast.reposition()

    def apply_theme(self, theme):
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(get_stylesheet(theme))

    def apply_background(self):
        path = str(self.settings.get("background_image_path") or "")
        if path and os.path.isfile(path):
            url = path.replace("\\", "/").replace('"', "")
            self._root.setStyleSheet(f'QWidget#Root {{ border-image: url("{url}") 0 0 0 0 stretch stretch; }}')
        else:
            self._root.setStyleSheet("")

    def apply_music(self):
        self._stop_music()
        directory = str(self.settings.get("music_dir") or "")
        if not directory or not os.path.isdir(directory):
            return
        player = MusicPlayer()
        if player.play(directory):
            self._music = player

    def reload_music(self):
        self.apply_music()

    def _stop_music(self):
        try:
            if self._music is not None:
                self._music.stop()
        except Exception:
            pass
        self._music = None

    def _restore_window(self):
        geometry = self.settings.get("window_geometry") or ""
        state = self.settings.get("window_state") or ""
        try:
            if geometry:
                self.restoreGeometry(QByteArray.fromBase64(str(geometry).encode("utf-8")))
        except Exception:
            pass
        try:
            if state:
                self.restoreState(QByteArray.fromBase64(str(state).encode("utf-8")))
        except Exception:
            pass

    def _restore_tab(self):
        try:
            index = int(self.settings.get("last_page_index") or 0)
        except Exception:
            index = 0
        if index < 0 or index >= self.tabs.count():
            index = 0
        self.switch_tab(index)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._restored_once:
            self._restored_once = True
            QTimer.singleShot(0, self._restore_tab)
            QTimer.singleShot(800, self._silent_update_check)

    def _silent_update_check(self):
        if os.environ.get("BSL_SMOKE_TEST") == "1":
            return
        if self._update_checked:
            return
        self._update_checked = True
        try:
            last = float(self.settings.get("last_update_check_ts") or 0)
        except Exception:
            last = 0
        if time.time() - last < 6 * 3600:
            return
        self.settings.set("last_update_check_ts", int(time.time()))
        self.settings.save()
        task = worker.UpdaterWorker("check", parent=self)
        self.attach_worker(task)
        task.check_done.connect(self._on_silent_update)
        task.start()

    def _on_silent_update(self, info):
        try:
            if str(info.get("version") or "") == str(self.settings.get("ignored_update_version") or ""):
                return
            self.dashboard.show_update(info)
            self.log("发现新版本：V" + str(info.get("version") or ""))
        except Exception:
            pass

    def closeEvent(self, event):
        deadline = time.time() + 2.0
        for task in list(self._workers):
            try:
                if not task.isRunning():
                    continue
                task.cancel()
                remaining = deadline - time.time()
                if remaining > 0:
                    task.wait(int(remaining * 1000))
            except Exception:
                pass
        for page in self._pages:
            try:
                page.save_to_settings()
            except Exception:
                pass
        try:
            self.settings.set(
                "window_geometry", self.saveGeometry().toBase64().data().decode("utf-8")
            )
            self.settings.set("window_state", self.saveState().toBase64().data().decode("utf-8"))
            self.settings.set("last_page_index", self.tabs.currentIndex())
        except Exception:
            pass
        self.settings.save()
        self._stop_music()
        super().closeEvent(event)
        os._exit(0)
