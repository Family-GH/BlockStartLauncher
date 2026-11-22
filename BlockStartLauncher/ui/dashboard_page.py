import os

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import (
    diagnostics,
    launcher_core,
    loader_installer,
    system_open,
    worker,
)
from core.icon_factory import create_app_icon, create_nav_icon
from ui.animations import Spinner
from ui.pixel_art import (
    PIXEL_BAD,
    PIXEL_GREEN,
    PIXEL_MUTED,
    PIXEL_YELLOW,
    PixelBackdrop,
    PixelProgressBar,
    StepIndicator,
)


class DashboardPage(QWidget):
    def __init__(self, settings, host, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.host = host
        self.current_instance = ""
        self._workers = []
        self._update_info = None
        self._launching = False
        self._java_path = ""
        self._current_task = None
        self._step_index = 0
        self._server_task = None
        self._health_rows = {}
        self._build_ui()
        self.on_instance_changed(self.host.current_instance_name())
        self.refresh_account()

    def _build_ui(self):
        self._backdrop = PixelBackdrop(self)
        self._backdrop.lower()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 10)
        layout.setSpacing(7)

        self.banner = QFrame()
        self.banner.setObjectName("Card")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        self.banner_label = QLabel("")
        self.banner_label.setObjectName("UpdateBanner")
        banner_layout.addWidget(self.banner_label, 1)
        self.view_update_btn = QPushButton("查看更新")
        self.view_update_btn.clicked.connect(self._open_update)
        banner_layout.addWidget(self.view_update_btn)
        self.ignore_update_btn = QPushButton("忽略此版本")
        self.ignore_update_btn.clicked.connect(self._ignore_update)
        banner_layout.addWidget(self.ignore_update_btn)
        self.banner.setVisible(False)
        layout.addWidget(self.banner)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("当前实例"))
        self.instance_combo = QComboBox()
        self.instance_combo.currentIndexChanged.connect(self._on_instance_combo)
        selector_row.addWidget(self.instance_combo, 1)
        self.new_instance_btn = QPushButton("新建实例")
        self.new_instance_btn.setObjectName("PrimaryButton")
        self.new_instance_btn.clicked.connect(lambda: self.host.instance_page.new_instance())
        selector_row.addWidget(self.new_instance_btn)
        layout.addLayout(selector_row)

        self.name_label = QLabel("尚未创建实例")
        self.name_label.setObjectName("BigTitle")
        layout.addWidget(self.name_label)
        self.version_label = QLabel("请先在实例页新建实例")
        self.version_label.setObjectName("VersionLabel")
        layout.addWidget(self.version_label)

        account_card = QFrame()
        account_card.setObjectName("Card")
        account_layout = QHBoxLayout(account_card)
        account_layout.setContentsMargins(16, 10, 16, 10)
        self.account_label = QLabel("当前账户：未选择")
        self.account_type_label = QLabel("")
        self.account_type_label.setObjectName("Muted")
        account_layout.addWidget(self.account_label)
        account_layout.addStretch(1)
        self.account_btn = QPushButton("管理账户")
        self.account_btn.clicked.connect(lambda: self.host.switch_tab(2))
        account_layout.addWidget(self.account_btn)
        account_layout.addWidget(self.account_type_label)
        layout.addWidget(account_card)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.instances_stat = self._make_stat_card("实例", "0", "instance")
        self.mods_stat = self._make_stat_card("Mod", "0", "mod")
        self.saves_stat = self._make_stat_card("存档", "0", "modpack")
        stats_row.addWidget(self.instances_stat[0])
        stats_row.addWidget(self.mods_stat[0])
        stats_row.addWidget(self.saves_stat[0])
        layout.addLayout(stats_row)

        flow_card = QFrame()
        flow_card.setObjectName("Card")
        flow_layout = QVBoxLayout(flow_card)
        flow_layout.setContentsMargins(12, 7, 12, 8)
        flow_layout.setSpacing(6)
        flow_header = QHBoxLayout()
        flow_title = QLabel("启动流程")
        flow_title.setObjectName("SectionTitle")
        flow_header.addWidget(flow_title)
        flow_header.addStretch(1)
        self.open_folder_btn = QPushButton("打开目录")
        self.open_folder_btn.setObjectName("GhostButton")
        self.open_folder_btn.clicked.connect(self.open_game_folder)
        flow_header.addWidget(self.open_folder_btn)
        self.backup_btn = QPushButton("备份存档")
        self.backup_btn.setObjectName("GhostButton")
        self.backup_btn.clicked.connect(self.backup_saves)
        flow_header.addWidget(self.backup_btn)
        self.repair_btn = QPushButton("修复工具")
        self.repair_btn.setObjectName("GhostButton")
        self.repair_btn.clicked.connect(lambda: self.host.switch_tab(6))
        flow_header.addWidget(self.repair_btn)
        flow_layout.addLayout(flow_header)
        self.steps = StepIndicator(["环境检查", "准备文件", "启动游戏"])
        flow_layout.addWidget(self.steps)
        layout.addWidget(flow_card)

        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(12)
        status_grid.setVerticalSpacing(12)
        status_grid.addWidget(self._build_environment_card(), 0, 0)
        status_grid.addWidget(self._build_server_card(), 0, 1)
        status_grid.setColumnStretch(0, 1)
        status_grid.setColumnStretch(1, 1)
        layout.addLayout(status_grid)

        layout.addStretch(1)

        self.launch_btn = QPushButton("启动游戏")
        self.launch_btn.setObjectName("LaunchButton")
        self.launch_btn.setIcon(create_app_icon())
        self.launch_btn.setIconSize(QSize(30, 30))
        self.launch_btn.clicked.connect(self.start_launch)
        layout.addWidget(self.launch_btn)

        self.progress = PixelProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.stop_btn = QPushButton("停止当前操作")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.stop_current)
        layout.addWidget(self.stop_btn)

        self.status_label = QLabel("准备就绪")
        self.status_label.setObjectName("Muted")
        self.status_label.setAlignment(Qt.AlignCenter)
        status_row = QHBoxLayout()
        status_row.addStretch(1)
        self.spinner = Spinner()
        status_row.addWidget(self.spinner)
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        layout.addLayout(status_row)
        self._backdrop.lower()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_backdrop"):
            self._backdrop.setGeometry(0, max(0, self.height() - 280), self.width(), min(280, self.height()))
            self._backdrop.lower()

    def _make_stat_card(self, title, value, kind):
        frame = QFrame()
        frame.setObjectName("Card")
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(12, 7, 12, 7)
        icon = QLabel()
        icon.setPixmap(create_nav_icon(kind).pixmap(22, 22))
        icon.setFixedSize(24, 24)
        frame_layout.addWidget(icon)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 19pt; font-weight: 700;")
        title_label = QLabel(title)
        title_label.setObjectName("Muted")
        text_layout.addWidget(value_label)
        text_layout.addWidget(title_label)
        frame_layout.addLayout(text_layout)
        frame_layout.addStretch(1)
        return frame, value_label

    def _build_environment_card(self):
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 7, 12, 8)
        header = QHBoxLayout()
        title = QLabel("运行环境")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.env_refresh_btn = QPushButton("刷新")
        self.env_refresh_btn.setObjectName("GhostButton")
        self.env_refresh_btn.clicked.connect(self.refresh_environment)
        header.addWidget(self.env_refresh_btn)
        layout.addLayout(header)
        for key, label in (("instance", "实例"), ("version", "游戏文件"),
                           ("account", "账户"), ("java", "Java")):
            row = QHBoxLayout()
            dot = QLabel("■")
            dot.setFixedWidth(12)
            dot.setStyleSheet("color: %s;" % PIXEL_MUTED)
            name = QLabel(label)
            name.setObjectName("Muted")
            text = QLabel("—")
            text.setWordWrap(True)
            row.addWidget(dot)
            row.addWidget(name)
            row.addWidget(text, 1)
            layout.addLayout(row)
            self._health_rows[key] = (dot, text)
        self.env_summary = QLabel("")
        self.env_summary.setObjectName("Muted")
        self.env_summary.setWordWrap(True)
        layout.addWidget(self.env_summary)
        return frame

    def _build_server_card(self):
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 7, 12, 8)
        header = QHBoxLayout()
        title = QLabel("服务器状态")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.server_refresh_btn = QPushButton("刷新")
        self.server_refresh_btn.setObjectName("GhostButton")
        self.server_refresh_btn.clicked.connect(lambda: self.refresh_server(force=True))
        header.addWidget(self.server_refresh_btn)
        layout.addLayout(header)
        self.server_name = QLabel("未设置自动进服服务器")
        self.server_name.setWordWrap(True)
        self.server_detail = QLabel("在设置或实例设置里填写地址")
        self.server_detail.setObjectName("Muted")
        self.server_detail.setWordWrap(True)
        self.server_motd = QLabel("")
        self.server_motd.setObjectName("Muted")
        self.server_motd.setWordWrap(True)
        layout.addWidget(self.server_name)
        layout.addWidget(self.server_detail)
        layout.addWidget(self.server_motd)
        return frame

    def refresh_instance_combo(self):
        instances = launcher_core.list_instances()
        self.instance_combo.blockSignals(True)
        self.instance_combo.clear()
        for instance in instances:
            label = instance["name"]
            if instance.get("version_id"):
                label += " · " + instance["version_id"]
            self.instance_combo.addItem(label, instance["name"])
        if not instances:
            self.instance_combo.addItem("还没有实例，点右侧“新建实例”开始", "")
        self.instance_combo.setEnabled(bool(instances))
        index = self.instance_combo.findData(self.current_instance)
        if index >= 0:
            self.instance_combo.setCurrentIndex(index)
        self.instance_combo.blockSignals(False)

    def _on_instance_combo(self, _index):
        name = self.instance_combo.currentData()
        if name and name != self.current_instance:
            self.host.select_instance(str(name))

    def refresh_account(self):
        account = self.host.current_account()
        if not account:
            self.account_label.setText("当前账户：未选择")
            self.account_type_label.setText("请先在账户页添加账户")
        else:
            self.account_label.setText("当前账户：" + str(account.get("username") or ""))
            self.account_type_label.setText("微软账户" if account.get("type") == "msa" else "离线账户")
        self.refresh_environment()

    def on_instance_changed(self, name):
        self.current_instance = name or ""
        instance = launcher_core.get_instance(self.current_instance) if self.current_instance else None
        if not instance:
            self.name_label.setText("欢迎使用 BlockStart")
            self.version_label.setText("点击下方“创建实例”，只需要选择版本即可")
            self.launch_btn.setText("创建实例")
        else:
            self.name_label.setText(instance["name"])
            version = instance["version_id"] or self.settings.get("last_version_id") or "未选择版本"
            self.version_label.setText("Minecraft " + str(version))
            self.launch_btn.setText("启动游戏")
        self.steps.reset()
        self.refresh_instance_combo()
        self.refresh_stats()
        self.refresh_account()
        self.refresh_server()
        self.refresh_environment()

    def refresh_stats(self):
        instances = launcher_core.list_instances()
        self.instances_stat[1].setText(str(len(instances)))
        stats = launcher_core.instance_stats(self.current_instance) if self.current_instance else {"mods": 0, "saves": 0}
        self.mods_stat[1].setText(str(stats.get("mods", 0)))
        self.saves_stat[1].setText(str(stats.get("saves", 0)))

    def refresh_environment(self):
        instance = launcher_core.get_instance(self.current_instance) if self.current_instance else None
        per_instance = launcher_core.get_instance_settings(instance["name"]) if instance else {}
        java_path = str(per_instance.get("java_path") or self.settings.get("java_path") or "")
        rows = diagnostics.instance_health(self.current_instance, self.host.current_account(), java_path)
        level_colors = {
            "good": PIXEL_GREEN,
            "warn": PIXEL_YELLOW,
            "bad": PIXEL_BAD,
        }
        for row in rows:
            widgets = self._health_rows.get(row.get("key"))
            if not widgets:
                continue
            dot, text = widgets
            dot.setStyleSheet("color: %s;" % level_colors.get(row.get("level"), PIXEL_MUTED))
            text.setText(str(row.get("text") or ""))
            text.setToolTip(str(row.get("detail") or ""))
        info = diagnostics.system_memory()
        disk = diagnostics.disk_space()
        if info.get("total_mb"):
            self.env_summary.setText(
                "内存 %.1f GB（可用 %.1f GB） · 游戏目录剩余 %.1f GB"
                % (info["total_mb"] / 1024.0, info.get("available_mb", 0) / 1024.0, disk.get("free_gb", 0))
            )
        else:
            self.env_summary.setText("游戏目录剩余 %.1f GB" % disk.get("free_gb", 0))

    def _server_address(self):
        instance = launcher_core.get_instance(self.current_instance) if self.current_instance else None
        per_instance = launcher_core.get_instance_settings(instance["name"]) if instance else {}
        address = str(per_instance.get("server") or self.settings.get("auto_join_server") or "").strip()
        port = str(per_instance.get("server_port") or self.settings.get("server_port") or "25565")
        return address, port

    def refresh_server(self, force=False):
        address, port = self._server_address()
        if not address:
            self.server_name.setText("未设置自动进服服务器")
            self.server_detail.setText("在设置或实例设置里填写地址即可显示在线人数")
            self.server_motd.setText("")
            self.server_refresh_btn.setEnabled(False)
            return
        self.server_refresh_btn.setEnabled(False)
        if self._server_task is not None and self._server_task.isRunning():
            return
        self.server_name.setText(address + ":" + port)
        self.server_detail.setText("正在连接…")
        self.server_motd.setText("")
        task = self._track(worker.ServerPingWorker(address, port))
        self._server_task = task
        task.finished_ok.connect(self._on_server_status)
        task.finished_error.connect(lambda message: self._on_server_status({"ok": False, "error": message}))
        task.finished.connect(lambda: setattr(self, "_server_task", None))
        task.start()

    def _on_server_status(self, result):
        self.server_refresh_btn.setEnabled(True)
        self._server_task = None
        if not result or not result.get("ok"):
            self.server_detail.setText("离线 / 无法连接")
            self.server_detail.setStyleSheet("color: %s;" % PIXEL_BAD)
            self.server_motd.setText(str((result or {}).get("error") or "服务器没有响应"))
            return
        self.server_detail.setStyleSheet("color: %s;" % PIXEL_GREEN)
        self.server_detail.setText(
            "%s/%s 在线 · %s ms · %s"
            % (
                result.get("players_online", 0),
                result.get("players_max", 0),
                result.get("latency_ms", 0),
                result.get("version") or "Minecraft",
            )
        )
        self.server_motd.setText(str(result.get("motd") or ""))
        if result.get("motd"):
            self.server_motd.setToolTip(str(result.get("motd")))

    def _set_busy(self, busy):
        self._launching = busy
        self.launch_btn.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.stop_btn.setVisible(busy)
        if not busy:
            self.stop_btn.setEnabled(True)
        self.spinner.set_running(busy)

    def stop_current(self):
        if self._current_task is not None:
            self._current_task.cancel()
            self.status_label.setText("正在停止…")
            self.stop_btn.setEnabled(False)

    def _set_progress(self, value, maximum):
        maximum = int(maximum or 0)
        if maximum <= 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, maximum)
            self.progress.setValue(int(value))

    def _track(self, task):
        if self.host is not None:
            self.host.attach_worker(task)
        else:
            self._workers.append(task)
        return task

    def _toast(self, text, kind="info"):
        try:
            self.host.toast(text, kind)
        except Exception:
            pass

    def _step(self, index, state="active"):
        self._step_index = index
        self.steps.set_step(index, state)
        if state == "done":
            for following in range(index + 1, 3):
                self.steps.set_step(following, "active")
                break

    def start_launch(self):
        if self._launching:
            return
        instance = launcher_core.get_instance(self.current_instance)
        if not instance:
            self.host.instance_page.new_instance()
            return
        if not instance.get("version_id"):
            QMessageBox.warning(self, "无法启动", "这个实例还没有选择游戏版本，请重新创建一个实例。")
            return
        account = self.host.current_account()
        if not account:
            answer = QMessageBox.question(
                self,
                "还没有账户",
                "启动游戏需要一个账户。要现在去添加离线账户吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self.host.switch_tab(2)
            return
        self._set_busy(True)
        self.steps.reset()
        self._step(0, "active")
        self.status_label.setText("正在检查 Java 环境")
        self._toast("开始检查启动环境", "info")
        instance_settings = launcher_core.get_instance_settings(instance["name"])
        game_version = launcher_core.instance_game_version(instance["name"]) or instance.get("version_id") or ""
        java_path = instance_settings.get("java_path") or self.settings.get("java_path") or ""
        required_major = launcher_core.required_java_major(game_version)
        java_task = self._track(
            worker.JavaSetupWorker(java_path, required_major=required_major, version_id=game_version)
        )
        self._current_task = java_task
        self.stop_btn.setEnabled(True)
        java_task.progress.connect(self._set_progress)
        java_task.status_changed.connect(self.status_label.setText)
        java_task.finished_ok.connect(self._on_java_ready)
        java_task.finished_error.connect(self._on_failure)
        java_task.start()

    def _on_java_ready(self, java_path):
        self._java_path = java_path
        self._step(0, "done")
        self._step(1, "active")
        instance = launcher_core.get_instance(self.current_instance)
        if not instance:
            self._on_failure("实例不存在")
            return
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        install_task = self._track(
            worker.InstallWorker(
                instance["version_id"],
                source=self.settings.get("download_source") or "auto",
            )
        )
        self._current_task = install_task
        self.stop_btn.setEnabled(True)
        install_task.progress.connect(self._set_progress)
        install_task.status_changed.connect(self.status_label.setText)
        install_task.finished_ok.connect(self._on_installed)
        install_task.finished_error.connect(self._on_failure)
        install_task.start()

    def _on_installed(self, _result):
        instance = launcher_core.get_instance(self.current_instance)
        if not instance:
            self._on_failure("实例不存在")
            return
        per_instance = launcher_core.get_instance_settings(instance["name"])
        if per_instance.get("loader") and not loader_installer.is_installed(
            per_instance.get("loader_version_id")
        ):
            self._step(1, "done")
            self._step(2, "active")
            self.status_label.setText(
                "正在安装 " + loader_installer.loader_label(per_instance.get("loader"))
            )
            self.progress.setRange(0, 0)
            loader_task = self._track(
                worker.LoaderInstallWorker(
                    per_instance.get("loader"),
                    launcher_core.instance_game_version(instance["name"]) or instance["version_id"],
                    per_instance.get("loader_version") or "",
                    self._java_path,
                )
            )
            self._current_task = loader_task
            self.stop_btn.setVisible(False)
            loader_task.progress.connect(self._set_progress)
            loader_task.status_changed.connect(self.status_label.setText)
            loader_task.finished_ok.connect(self._on_loader_ready)
            loader_task.finished_error.connect(self._on_failure)
            loader_task.start()
            return
        self._step(1, "done")
        self._step(2, "active")
        self._launch_instance()

    def _on_loader_ready(self, result):
        instance = launcher_core.get_instance(self.current_instance)
        version_id = str((result or {}).get("version_id") or "")
        if instance and version_id:
            try:
                launcher_core.update_instance_settings(
                    instance["name"], {"loader_version_id": version_id}
                )
                self.host.log("加载器已安装：" + version_id)
            except Exception as exc:
                self._on_failure("保存加载器信息失败：" + str(exc))
                return
        self._launch_instance()

    def _launch_instance(self):
        instance = launcher_core.get_instance(self.current_instance)
        account = self.host.current_account()
        if not instance or not account:
            self._on_failure("实例或账户信息丢失")
            return
        per_instance = launcher_core.get_instance_settings(instance["name"])
        memory = int(per_instance.get("max_memory_mb") or self.settings.get("max_memory_mb") or 2048)
        jvm_args = per_instance.get("jvm_args")
        if jvm_args is None or jvm_args == "":
            jvm_args = self.settings.get("jvm_args") or ""
        width = int(per_instance.get("width") or self.settings.get("window_width") or 854)
        height = int(per_instance.get("height") or self.settings.get("window_height") or 480)
        fullscreen = bool(per_instance.get("fullscreen") or self.settings.get("fullscreen") or False)
        game_args = per_instance.get("game_args") or self.settings.get("game_args") or ""
        server = per_instance.get("server") or self.settings.get("auto_join_server") or ""
        server_port = per_instance.get("server_port") or self.settings.get("server_port") or "25565"
        launch_version = per_instance.get("loader_version_id") or launcher_core.instance_game_version(instance["name"]) or instance["version_id"]
        if not launch_version:
            self._on_failure("这个实例没有可启动的游戏版本")
            return
        self.status_label.setText("正在启动游戏")
        self.progress.setRange(0, 0)
        launch_task = self._track(
            worker.LaunchWorker(
                launch_version,
                instance["path"],
                self._java_path,
                account.get("id"),
                memory,
                jvm_args,
                self.settings.get("ms_client_id") or "",
                game_settings={
                    "width": width,
                    "height": height,
                    "fullscreen": fullscreen,
                    "game_args": game_args,
                    "server": server,
                    "server_port": server_port,
                },
            )
        )
        self._current_task = launch_task
        self.stop_btn.setVisible(False)
        launch_task.status_changed.connect(self.status_label.setText)
        launch_task.finished_ok.connect(self._on_launched)
        launch_task.finished_error.connect(self._on_failure)
        launch_task.start()

    def _on_launched(self, result):
        self._set_busy(False)
        for index in range(3):
            self.steps.set_step(index, "done")
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.status_label.setText("游戏已启动（PID " + str(result.get("pid")) + "）")
        self._toast("游戏已启动", "success")
        if self.host:
            self.host.log("游戏已启动：" + str(self.current_instance))

    def _on_failure(self, message):
        self._set_busy(False)
        self.steps.set_step(self._step_index, "error")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status_label.setText("启动失败：" + str(message))
        self._toast("启动失败：" + str(message), "error", 4200)
        if self.host:
            self.host.log("启动失败：" + str(message))
        text = str(message)
        if "Java" in text or "java" in text:
            answer = QMessageBox.question(
                self,
                "需要选择 Java",
                text + "\n\n要现在打开设置页选择电脑里的 Java 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self.host.switch_tab(7)

    def open_game_folder(self):
        instance = launcher_core.get_instance(self.current_instance) if self.current_instance else None
        if not instance:
            QMessageBox.information(self, "打开目录", "请先选择一个实例。")
            return
        ok, error = system_open.open_folder(instance["path"])
        if not ok:
            QMessageBox.warning(self, "无法打开目录", "路径：\n%s\n\n%s" % (instance["path"], error))

    def backup_saves(self):
        if self._launching:
            return
        instance = launcher_core.get_instance(self.current_instance) if self.current_instance else None
        if not instance:
            QMessageBox.information(self, "备份存档", "请先选择一个实例。")
            return
        self._set_busy(True)
        self.steps.reset()
        self._step(0, "done")
        self._step(1, "active")
        self.status_label.setText("正在备份存档")
        task = self._track(worker.SaveBackupWorker(instance["name"]))
        self._current_task = task
        task.progress.connect(self._set_progress)
        task.finished_ok.connect(self._on_backup_done)
        task.finished_error.connect(self._on_backup_error)
        task.start()

    def _on_backup_done(self, result):
        self._set_busy(False)
        self.steps.set_step(1, "done")
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.status_label.setText("备份完成：" + str((result or {}).get("count", 0)) + " 个文件")
        self._toast("存档备份完成", "success")

    def _on_backup_error(self, message):
        self._set_busy(False)
        self.steps.set_step(1, "error")
        self.status_label.setText("备份失败：" + str(message))
        self._toast("备份失败：" + str(message), "error", 3600)

    def show_update(self, info):
        self._update_info = info
        self.banner_label.setText("发现新版本 V" + str(info.get("version") or ""))
        self.banner.setVisible(True)

    def _open_update(self):
        if not self._update_info:
            return
        url = self._update_info.get("html_url") or ""
        if not url:
            QMessageBox.information(self, "更新", "这个版本没有提供发布页链接。")
            return
        ok, error = system_open.open_url(url)
        if not ok:
            QMessageBox.warning(
                self,
                "无法打开更新页面",
                "浏览器没有成功打开：\n%s\n\n%s" % (url, error),
            )

    def _ignore_update(self):
        if self._update_info:
            self.settings.set("ignored_update_version", str(self._update_info.get("version") or ""))
            self.settings.save()
        self.banner.setVisible(False)

    def save_to_settings(self):
        instance = launcher_core.get_instance(self.current_instance) if self.current_instance else None
        if instance:
            self.settings.set("last_instance", instance["name"])
            self.settings.set(
                "last_version_id", instance.get("version_id") or self.settings.get("last_version_id") or ""
            )

