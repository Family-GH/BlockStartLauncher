import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import config
from core import crash_analyzer, diagnostics, java_manager, launcher_core, system_open, updater, worker


class SettingsPage(QWidget):
    def __init__(self, settings, host, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.host = host
        self._workers = []
        self._loading = True
        self._update_info = None
        self._build_ui()
        self._load_values()
        self._loading = False
        self._java_loaded = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self._java_loaded:
            self._java_loaded = True
            self._start_java_detect()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)
        title = QLabel("设置")
        title.setStyleSheet("font-size: 17pt; font-weight: 700;")
        layout.addWidget(title)

        appearance = QGroupBox("外观")
        appearance_layout = QVBoxLayout(appearance)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("主题"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("深色", "dark")
        self.theme_combo.addItem("浅色", "light")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo, 1)
        appearance_layout.addLayout(theme_row)
        self.animations_check = QCheckBox("启用页面淡入与加载动画（关闭可省一点性能）")
        self.animations_check.toggled.connect(self._on_animations_changed)
        appearance_layout.addWidget(self.animations_check)
        layout.addWidget(appearance)

        performance = QGroupBox("性能")
        performance_layout = QVBoxLayout(performance)
        memory_row = QHBoxLayout()
        memory_row.addWidget(QLabel("游戏内存"))
        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(512, 8192)
        self.memory_spin.setSingleStep(256)
        self.memory_spin.setSuffix(" MB")
        self.memory_spin.valueChanged.connect(self._on_memory_changed)
        memory_row.addWidget(self.memory_spin, 1)
        performance_layout.addLayout(memory_row)
        self.memory_hint = QLabel("")
        self.memory_hint.setObjectName("Muted")
        self.memory_hint.setWordWrap(True)
        performance_layout.addWidget(self.memory_hint)
        jvm_row = QHBoxLayout()
        jvm_row.addWidget(QLabel("高级启动参数"))
        self.jvm_edit = QLineEdit()
        self.jvm_edit.setPlaceholderText("不懂请留空")
        self.jvm_edit.editingFinished.connect(self._on_jvm_changed)
        jvm_row.addWidget(self.jvm_edit, 1)
        performance_layout.addLayout(jvm_row)
        layout.addWidget(performance)

        window_group = QGroupBox("游戏窗口与启动")
        window_layout = QVBoxLayout(window_group)
        window_hint = QLabel("这里的设置会作为所有实例的默认值；单个实例可以在“实例设置”里覆盖。")
        window_hint.setObjectName("Muted")
        window_hint.setWordWrap(True)
        window_layout.addWidget(window_hint)
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("窗口大小"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 7680)
        self.width_spin.setSpecialValueText("默认")
        self.width_spin.valueChanged.connect(self._on_window_changed)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 4320)
        self.height_spin.setSpecialValueText("默认")
        self.height_spin.valueChanged.connect(self._on_window_changed)
        size_row.addWidget(self.width_spin)
        size_row.addWidget(QLabel("×"))
        size_row.addWidget(self.height_spin)
        self.fullscreen_check = QCheckBox("全屏启动")
        self.fullscreen_check.toggled.connect(self._on_fullscreen_changed)
        size_row.addWidget(self.fullscreen_check)
        size_row.addStretch(1)
        window_layout.addLayout(size_row)
        args_row = QHBoxLayout()
        args_row.addWidget(QLabel("额外游戏参数"))
        self.game_args_edit = QLineEdit()
        self.game_args_edit.setPlaceholderText("例如 --demo，留空即可")
        self.game_args_edit.editingFinished.connect(self._on_game_args_changed)
        args_row.addWidget(self.game_args_edit, 1)
        window_layout.addLayout(args_row)
        server_row = QHBoxLayout()
        server_row.addWidget(QLabel("自动进入服务器"))
        self.server_edit = QLineEdit()
        self.server_edit.setPlaceholderText("服务器地址，留空则不自动进入")
        self.server_edit.editingFinished.connect(self._on_server_changed)
        server_row.addWidget(self.server_edit, 1)
        server_row.addWidget(QLabel("端口"))
        self.server_port_edit = QLineEdit()
        self.server_port_edit.setPlaceholderText("25565")
        self.server_port_edit.editingFinished.connect(self._on_server_changed)
        server_row.addWidget(self.server_port_edit)
        window_layout.addLayout(server_row)
        layout.addWidget(window_group)

        download = QGroupBox("下载")
        download_layout = QVBoxLayout(download)
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("下载线路"))
        self.source_combo = QComboBox()
        self.source_combo.addItem("自动选择（镜像优先）", "auto")
        self.source_combo.addItem("BMCLAPI 镜像", "bmclapi")
        self.source_combo.addItem("官方源", "official")
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        source_row.addWidget(self.source_combo, 1)
        download_layout.addLayout(source_row)
        layout.addWidget(download)

        java_group = QGroupBox("Java 运行环境")
        java_layout = QVBoxLayout(java_group)
        java_hint = QLabel("启动器会自动查找电脑里的 Java。找不到或想用指定版本时，点“手动选择”即可。")
        java_hint.setObjectName("Muted")
        java_hint.setWordWrap(True)
        java_layout.addWidget(java_hint)
        java_row = QHBoxLayout()
        self.java_combo = QComboBox()
        self.java_combo.addItem("自动检测（推荐）", "")
        self.java_combo.currentIndexChanged.connect(self._on_java_changed)
        java_row.addWidget(self.java_combo, 1)
        self.java_detect_btn = QPushButton("重新检测")
        self.java_detect_btn.clicked.connect(self._start_java_detect)
        java_row.addWidget(self.java_detect_btn)
        self.java_browse_btn = QPushButton("手动选择")
        self.java_browse_btn.setObjectName("PrimaryButton")
        self.java_browse_btn.clicked.connect(self._browse_java)
        java_row.addWidget(self.java_browse_btn)
        java_layout.addLayout(java_row)
        self.java_label = QLabel("正在检测…")
        self.java_label.setObjectName("Muted")
        self.java_label.setWordWrap(True)
        java_layout.addWidget(self.java_label)
        layout.addWidget(java_group)

        game_group = QGroupBox("游戏文件位置")
        game_layout = QVBoxLayout(game_group)
        game_hint = QLabel("下载的游戏版本、实例、存档和模组都放在这里。可以换到空间更大的磁盘。")
        game_hint.setObjectName("Muted")
        game_hint.setWordWrap(True)
        game_layout.addWidget(game_hint)
        game_row = QHBoxLayout()
        self.game_dir_edit = QLineEdit()
        self.game_dir_edit.setReadOnly(True)
        game_row.addWidget(self.game_dir_edit, 1)
        self.game_dir_btn = QPushButton("选择文件夹")
        self.game_dir_btn.setObjectName("PrimaryButton")
        self.game_dir_btn.clicked.connect(self._choose_game_dir)
        game_row.addWidget(self.game_dir_btn)
        self.open_data_btn = QPushButton("打开数据目录")
        self.open_data_btn.clicked.connect(self._open_data_dir)
        game_row.addWidget(self.open_data_btn)
        game_layout.addLayout(game_row)
        history_row = QHBoxLayout()
        history_row.addWidget(QLabel("用过的位置"))
        self.game_dir_combo = QComboBox()
        self.game_dir_combo.setToolTip("快速切换到以前用过的游戏目录")
        self.game_dir_combo.activated.connect(self._on_game_dir_history)
        history_row.addWidget(self.game_dir_combo, 1)
        game_layout.addLayout(history_row)
        layout.addWidget(game_group)

        personal = QGroupBox("背景与音乐（可选）")
        personal_layout = QVBoxLayout(personal)
        bg_row = QHBoxLayout()
        bg_row.addWidget(QLabel("背景图片"))
        self.background_edit = QLineEdit()
        self.background_edit.setReadOnly(True)
        bg_row.addWidget(self.background_edit, 1)
        bg_browse = QPushButton("浏览")
        bg_browse.clicked.connect(self._choose_background)
        bg_row.addWidget(bg_browse)
        bg_clear = QPushButton("清除")
        bg_clear.clicked.connect(self._clear_background)
        bg_row.addWidget(bg_clear)
        personal_layout.addLayout(bg_row)
        music_row = QHBoxLayout()
        music_row.addWidget(QLabel("音乐目录"))
        self.music_edit = QLineEdit()
        self.music_edit.setReadOnly(True)
        music_row.addWidget(self.music_edit, 1)
        music_browse = QPushButton("浏览")
        music_browse.clicked.connect(self._choose_music)
        music_row.addWidget(music_browse)
        music_clear = QPushButton("清除")
        music_clear.clicked.connect(self._clear_music)
        music_row.addWidget(music_clear)
        personal_layout.addLayout(music_row)
        layout.addWidget(personal)

        account_group = QGroupBox("微软账户登录（可选）")
        account_layout = QVBoxLayout(account_group)
        account_hint = QLabel("已经内置登录服务，普通玩家不用填这里。只有登录失败时才需要填写自己的应用 ID。")
        account_hint.setObjectName("Muted")
        account_hint.setWordWrap(True)
        account_layout.addWidget(account_hint)
        client_row = QHBoxLayout()
        client_row.addWidget(QLabel("应用 ID"))
        self.client_edit = QLineEdit()
        self.client_edit.setPlaceholderText("一般不用填写")
        self.client_edit.editingFinished.connect(self._on_client_id_changed)
        client_row.addWidget(self.client_edit, 1)
        account_layout.addLayout(client_row)
        layout.addWidget(account_group)

        tools = QGroupBox("诊断与帮助")
        tools_layout = QHBoxLayout(tools)
        crash_btn = QPushButton("查看崩溃原因")
        crash_btn.clicked.connect(self._show_crash_summary)
        tools_layout.addWidget(crash_btn)
        logs_btn = QPushButton("打开日志文件夹")
        logs_btn.clicked.connect(self._open_logs)
        tools_layout.addWidget(logs_btn)
        tools_layout.addStretch(1)
        layout.addWidget(tools)

        update_group = QGroupBox("启动器更新")
        update_layout = QVBoxLayout(update_group)
        version_row = QHBoxLayout()
        self.current_version_label = QLabel("当前版本：V" + config.LAUNCHER_VERSION + " · " + config.LAUNCHER_AUTHOR)
        version_row.addWidget(self.current_version_label, 1)
        self.check_update_btn = QPushButton("检查更新")
        self.check_update_btn.setObjectName("PrimaryButton")
        self.check_update_btn.clicked.connect(self._check_update)
        version_row.addWidget(self.check_update_btn)
        update_layout.addLayout(version_row)
        sources_label = QLabel(
            "更新渠道：默认从 GitHub Releases 检查；也可以在下面添加其他 JSON 清单源（每行一个 URL），"
            "启动器会自动选择版本最高的来源。"
        )
        sources_label.setObjectName("Muted")
        sources_label.setWordWrap(True)
        update_layout.addWidget(sources_label)
        self.update_sources_edit = QPlainTextEdit()
        self.update_sources_edit.setMaximumHeight(66)
        self.update_sources_edit.setPlaceholderText("https://example.com/blockstart/update.json")
        update_layout.addWidget(self.update_sources_edit)
        sources_row = QHBoxLayout()
        sources_row.addStretch(1)
        save_sources_btn = QPushButton("保存更新源")
        save_sources_btn.clicked.connect(self._save_update_sources)
        sources_row.addWidget(save_sources_btn)
        update_layout.addLayout(sources_row)
        self.update_result = QLabel("")
        self.update_result.setObjectName("Muted")
        self.update_result.setWordWrap(True)
        update_layout.addWidget(self.update_result)
        self.update_progress = QProgressBar()
        self.update_progress.setVisible(False)
        update_layout.addWidget(self.update_progress)
        self.download_update_btn = QPushButton("下载并更新")
        self.download_update_btn.setVisible(False)
        self.download_update_btn.clicked.connect(self._download_update)
        update_layout.addWidget(self.download_update_btn)
        layout.addWidget(update_group)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _load_values(self):
        theme = self.settings.get("theme") or "dark"
        index = self.theme_combo.findData(theme)
        self.theme_combo.setCurrentIndex(index if index >= 0 else 0)
        self.animations_check.blockSignals(True)
        self.animations_check.setChecked(bool(self.settings.get("animations", True)))
        self.animations_check.blockSignals(False)
        self.memory_spin.setValue(int(self.settings.get("max_memory_mb") or 2048))
        memory = diagnostics.system_memory()
        if memory.get("total_mb"):
            self.memory_hint.setText(
                "电脑内存约 %.1f GB，推荐给游戏 %s MB；设置过大会让系统变慢。"
                % (memory["total_mb"] / 1024.0, diagnostics.recommended_memory())
            )
        else:
            self.memory_hint.setText("无法读取系统内存，建议 2048–4096 MB。")
        self.jvm_edit.setText(str(self.settings.get("jvm_args") or ""))
        source = self.settings.get("download_source") or "auto"
        index = self.source_combo.findData(source)
        self.source_combo.setCurrentIndex(index if index >= 0 else 0)
        self.background_edit.setText(str(self.settings.get("background_image_path") or ""))
        self.music_edit.setText(str(self.settings.get("music_dir") or ""))
        self.client_edit.setText(str(self.settings.get("ms_client_id") or ""))
        sources = self.settings.get("update_sources") or []
        if isinstance(sources, str):
            sources = [sources]
        self.update_sources_edit.setPlainText("\n".join(str(item) for item in sources if item))
        self.game_dir_edit.setText(config.minecraft_dir())
        self._refresh_game_dirs()
        self.width_spin.blockSignals(True)
        self.height_spin.blockSignals(True)
        self.width_spin.setValue(int(self.settings.get("window_width") or 854))
        self.height_spin.setValue(int(self.settings.get("window_height") or 480))
        self.width_spin.blockSignals(False)
        self.height_spin.blockSignals(False)
        self.fullscreen_check.blockSignals(True)
        self.fullscreen_check.setChecked(bool(self.settings.get("fullscreen")))
        self.fullscreen_check.blockSignals(False)
        self.game_args_edit.setText(str(self.settings.get("game_args") or ""))
        self.server_edit.setText(str(self.settings.get("auto_join_server") or ""))
        self.server_port_edit.setText(str(self.settings.get("server_port") or "25565"))

    def _on_window_changed(self, _value=None):
        self.settings.set("window_width", int(self.width_spin.value()))
        self.settings.set("window_height", int(self.height_spin.value()))
        self.settings.save()

    def _on_fullscreen_changed(self, checked):
        self.settings.set("fullscreen", bool(checked))
        self.settings.save()

    def _on_game_args_changed(self):
        self.settings.set("game_args", self.game_args_edit.text().strip())
        self.settings.save()

    def _on_server_changed(self):
        self.settings.set("auto_join_server", self.server_edit.text().strip())
        port = self.server_port_edit.text().strip() or "25565"
        self.settings.set("server_port", port)
        self.settings.save()

    def _refresh_game_dirs(self):
        current = os.path.abspath(config.minecraft_dir())
        directories = self.settings.get("game_dirs")
        if not isinstance(directories, list):
            directories = []
        options = []
        for item in directories + [current]:
            path = os.path.abspath(str(item or ""))
            if path and path not in options:
                options.append(path)
        self.game_dir_combo.blockSignals(True)
        self.game_dir_combo.clear()
        for path in options:
            self.game_dir_combo.addItem(self._short_path(path), path)
        index = self.game_dir_combo.findData(current)
        if index >= 0:
            self.game_dir_combo.setCurrentIndex(index)
        self.game_dir_combo.blockSignals(False)

    def _on_game_dir_history(self, index):
        path = str(self.game_dir_combo.itemData(index) or "")
        if not path or os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(config.minecraft_dir())):
            return
        answer = QMessageBox.question(
            self,
            "切换游戏目录",
            "确定切换到下面的游戏目录吗？\n" + path + "\n\n旧目录里的游戏不会自动搬过去。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            self._refresh_game_dirs()
            return
        if self.host:
            self.host.change_game_dir(path)
        self.game_dir_edit.setText(config.minecraft_dir())
        self._refresh_game_dirs()

    def _store(self, key, value):
        self.settings.set(key, value)
        self.settings.save()

    def _on_theme_changed(self, _index):
        if self._loading:
            return
        theme = self.theme_combo.currentData() or "dark"
        self._store("theme", theme)
        if self.host:
            self.host.apply_theme(theme)
            self.host.toast("主题已切换", "success")

    def _on_animations_changed(self, checked):
        if self._loading:
            return
        self._store("animations", bool(checked))
        if self.host:
            self.host.toast("动画已" + ("开启" if checked else "关闭"), "info")

    def _on_memory_changed(self, value):
        if self._loading:
            return
        self._store("max_memory_mb", int(value))

    def _on_jvm_changed(self):
        if self._loading:
            return
        self._store("jvm_args", self.jvm_edit.text().strip())

    def _on_source_changed(self, _index):
        if self._loading:
            return
        self._store("download_source", self.source_combo.currentData() or "auto")

    def _on_client_id_changed(self):
        if self._loading:
            return
        self._store("ms_client_id", self.client_edit.text().strip())

    def _start_java_detect(self):
        self.java_detect_btn.setEnabled(False)
        self.java_label.setText("正在检测电脑中的 Java，请稍候…")
        task = worker.JavaDetectWorker(self)
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        task.finished_ok.connect(self._on_java_list)
        task.finished_error.connect(lambda _msg: self._on_java_list([]))
        task.start()

    def _on_java_list(self, items):
        self.java_detect_btn.setEnabled(True)
        self._loading = True
        current = str(self.settings.get("java_path") or "")
        self.java_combo.clear()
        self.java_combo.addItem("自动检测（推荐）", "")
        paths = []
        for info in items or []:
            label = f"Java {info['version']} — {self._short_path(info['path'])}"
            self.java_combo.addItem(label, info["path"])
            self.java_combo.setItemData(
                self.java_combo.count() - 1, info["path"], Qt.ToolTipRole
            )
            paths.append(info["path"])
        if current and current not in paths:
            self.java_combo.addItem("已保存：" + self._short_path(current), current)
        index = self.java_combo.findData(current) if current else 0
        self.java_combo.setCurrentIndex(index if index >= 0 else 0)
        self._loading = False
        if items:
            self.java_label.setText(f"找到 {len(items)} 个 Java，已自动选择最合适的一个。")
        elif current:
            self.java_label.setText("没有自动检测到 Java，已保留你上次手动选择的 Java。")
        else:
            self.java_label.setText("没有检测到 Java。可以点“手动选择”，或让启动器自动下载。")

    def _on_java_changed(self, _index):
        if self._loading:
            return
        path = str(self.java_combo.currentData() or "")
        self._store("java_path", path)
        if path:
            info = java_manager.java_info(path)
            if info:
                suffix = "（版本较旧，新版游戏可能无法启动）" if info["major"] < 17 else ""
                self.java_label.setText(f"将使用：Java {info['version']}{suffix}")
            else:
                self.java_label.setText("这个 Java 似乎不可用，请重新选择。")
        else:
            self.java_label.setText("将在启动时自动检测 Java。")

    def _browse_java(self):
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "选择 java.exe",
            "",
            "Java 程序 (java.exe javaw.exe);;所有文件 (*.*)",
        )
        if not path:
            return
        info = java_manager.java_info(path)
        if info is None:
            QMessageBox.warning(
                self,
                "无法使用",
                "这个文件不是可用的 Java。请选择 Java 安装目录里的 bin\\java.exe。",
            )
            return
        self._loading = True
        index = self.java_combo.findData(path)
        if index < 0:
            self.java_combo.addItem(f"Java {info['version']} — {self._short_path(path)}", path)
            index = self.java_combo.count() - 1
        self.java_combo.setCurrentIndex(index)
        self._loading = False
        self._store("java_path", path)
        suffix = "（版本较旧，新版游戏可能无法启动）" if info["major"] < 17 else ""
        self.java_label.setText("将使用：Java " + info["version"] + suffix + "（已手动选择）")

    def _short_path(self, path):
        text = str(path or "")
        if len(text) <= 60:
            return text
        parts = text.replace("/", "\\").split("\\")
        return "...\\" + "\\".join(parts[-3:])

    def _choose_game_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择游戏文件保存位置")
        if not path:
            return
        answer = QMessageBox.question(
            self,
            "切换游戏目录",
            "切换后，新下载的版本和新建的实例会保存到新目录。\n"
            "旧目录里的游戏不会自动搬过去，需要手动复制。\n\n确定切换吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        if self.host:
            self.host.change_game_dir(path)
        self.game_dir_edit.setText(config.minecraft_dir())
        self._refresh_game_dirs()
        QMessageBox.information(self, "已切换", "游戏目录已切换到：\n" + config.minecraft_dir())

    def _open_data_dir(self):
        path = config.data_dir()
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "打开数据目录失败", "无法创建数据目录：\n" + str(exc))
            return
        ok, error = system_open.open_folder(path)
        if not ok:
            QMessageBox.warning(
                self,
                "打开数据目录失败",
                "无法用资源管理器打开：\n%s\n\n%s" % (path, error),
            )

    def _on_java_detected(self, _path):
        self._start_java_detect()

    def _choose_background(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, "选择背景图片", "", "图片 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        self.background_edit.setText(path)
        self._store("background_image_path", path)
        if self.host:
            self.host.apply_background()

    def _clear_background(self):
        self.background_edit.setText("")
        self._store("background_image_path", "")
        if self.host:
            self.host.apply_background()

    def _choose_music(self):
        path = QFileDialog.getExistingDirectory(self, "选择背景音乐目录")
        if not path:
            return
        self.music_edit.setText(path)
        self._store("music_dir", path)
        if self.host:
            self.host.reload_music()

    def _clear_music(self):
        self.music_edit.setText("")
        self._store("music_dir", "")
        if self.host:
            self.host.reload_music()

    def _show_crash_summary(self):
        name = self.host.current_instance_name() if self.host else ""
        instance = launcher_core.get_instance(name) if name else None
        if not instance:
            QMessageBox.information(self, "崩溃分析", "请先选择一个实例。")
            return
        result = crash_analyzer.analyze_crash(instance["path"])
        if not result:
            QMessageBox.information(self, "崩溃分析", "该实例下没有找到崩溃报告或 latest.log。")
            return
        lines = ["原因：" + str(result.get("summary") or "未知")]
        for match in result.get("matches") or []:
            lines.append("")
            lines.append("• " + str(match.get("title")))
            lines.append("  " + str(match.get("advice")))
        box = QMessageBox(self)
        box.setWindowTitle("崩溃分析摘要")
        box.setText("\n".join(lines))
        box.setDetailedText(str(result.get("tail") or ""))
        box.exec()

    def _open_logs(self):
        path = os.path.join(config.minecraft_dir(), "logs")
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            path = config.base_dir()
        ok, error = system_open.open_folder(path)
        if not ok:
            QMessageBox.warning(
                self,
                "打开日志文件夹失败",
                "无法用资源管理器打开：\n%s\n\n%s" % (path, error),
            )

    def _save_update_sources(self):
        sources = [
            line.strip()
            for line in self.update_sources_edit.toPlainText().replace(",", "\n").splitlines()
            if line.strip()
        ]
        self.settings.set("update_sources", sources)
        self.settings.save()
        self.update_result.setText(
            "已保存 " + str(len(sources)) + " 个自定义更新源；同时仍会使用 GitHub。" if sources else "已恢复仅使用 GitHub 更新。"
        )
        if self.host:
            self.host.toast("更新源已保存", "success")

    def _check_update(self):
        self.check_update_btn.setEnabled(False)
        self.update_result.setText("正在检查更新…")
        self.download_update_btn.setVisible(False)
        sources = self.settings.get("update_sources") or []
        task = worker.UpdaterWorker("check", sources=sources, parent=self)
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        task.check_done.connect(self._on_update_found)
        task.check_empty.connect(self._on_update_empty)
        task.finished_error.connect(self._on_update_error)
        task.start()

    def _on_update_found(self, info):
        self.check_update_btn.setEnabled(True)
        self._update_info = info
        self.update_result.setText(
            f"发现新版本 V{info.get('version')}（当前 V{config.LAUNCHER_VERSION}，来源：{info.get('source') or 'GitHub'}）"
        )
        self.download_update_btn.setVisible(True)

    def _on_update_empty(self):
        self.check_update_btn.setEnabled(True)
        self.update_result.setText("当前已是最新版本。")
        self.download_update_btn.setVisible(False)

    def _on_update_error(self, message):
        self.check_update_btn.setEnabled(True)
        self.update_result.setText("检查更新失败：" + str(message))

    def _download_update(self):
        if not self._update_info:
            return
        answer = QMessageBox.question(
            self,
            "下载更新",
            f"确定下载并更新到 V{self._update_info.get('version')} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        self.download_update_btn.setEnabled(False)
        self.check_update_btn.setEnabled(False)
        self.update_progress.setVisible(True)
        self.update_progress.setRange(0, 0)
        self.update_result.setText("正在下载更新…")
        task = worker.UpdaterWorker("download", self._update_info, parent=self)
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        task.progress.connect(self._on_update_progress)
        task.finished_ok.connect(self._on_update_downloaded)
        task.finished_error.connect(self._on_update_download_error)
        task.start()

    def _on_update_progress(self, done, total):
        if total <= 0:
            self.update_progress.setRange(0, 0)
        else:
            self.update_progress.setRange(0, total)
            self.update_progress.setValue(done)

    def _on_update_downloaded(self, path):
        self.download_update_btn.setEnabled(True)
        self.check_update_btn.setEnabled(True)
        self.update_progress.setVisible(False)
        self.update_result.setText("更新包已下载：" + str(path))
        answer = QMessageBox.question(
            self,
            "安装更新",
            "更新包已下载，是否立即重启并安装？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            updater.apply_update(path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "无法自动更新",
                str(exc) + "\n\n你可以手动用下载的文件替换当前程序。\n" + str(path),
            )

    def _on_update_download_error(self, message):
        self.download_update_btn.setEnabled(True)
        self.check_update_btn.setEnabled(True)
        self.update_progress.setVisible(False)
        self.update_result.setText("下载更新失败：" + str(message))

    def save_to_settings(self):
        return
