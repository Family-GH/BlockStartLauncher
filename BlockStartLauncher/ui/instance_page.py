import os
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core import launcher_core, loader_installer, save_manager, system_open, worker
from core.icon_factory import create_nav_icon


def _version_label(entry):
    version_id = entry.get("id") or ""
    if entry.get("installed"):
        return f"{version_id}（已安装，可直接玩）"
    if entry.get("type") == "release":
        return f"{version_id}（正式版）"
    if entry.get("type") == "snapshot":
        return f"{version_id}（快照版）"
    return f"{version_id}（旧版本）"


class NewInstanceDialog(QDialog):
    def __init__(self, versions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建实例")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        self.name_edit = QLineEdit("我的世界")
        self.version_combo = QComboBox()
        for entry in versions:
            self.version_combo.addItem(_version_label(entry), entry.get("id") or "")
        default_index = 0
        for index, entry in enumerate(versions):
            if entry.get("type") == "release" and not entry.get("installed"):
                default_index = index
                break
        self.version_combo.setCurrentIndex(default_index)
        self.loader_combo = QComboBox()
        for loader_id, label in loader_installer.LOADERS:
            self.loader_combo.addItem(label, loader_id)
        form.addWidget(QLabel("实例名称"), 0, 0)
        form.addWidget(self.name_edit, 0, 1)
        form.addWidget(QLabel("游戏版本"), 1, 0)
        form.addWidget(self.version_combo, 1, 1)
        form.addWidget(QLabel("模组加载器"), 2, 0)
        form.addWidget(self.loader_combo, 2, 1)
        layout.addLayout(form)
        note = QLabel(
            "版本从列表里选择即可。第一次启动会自动下载游戏文件；"
            "如果选了 Fabric/Forge 等加载器，也会在启动前自动安装。"
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("创建")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        name = self.name_edit.text().strip() or "我的世界"
        version_id = str(self.version_combo.currentData() or "").strip()
        loader_id = str(self.loader_combo.currentData() or "")
        return name, version_id, loader_id


class VersionPickerDialog(QDialog):
    def __init__(self, versions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("下载游戏版本")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        hint = QLabel("选择一个版本下载。下载完成后，新建实例时可以直接选择它。")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.version_combo = QComboBox()
        for entry in versions:
            self.version_combo.addItem(_version_label(entry), entry.get("id") or "")
        default_index = 0
        for index, entry in enumerate(versions):
            if entry.get("type") == "release" and not entry.get("installed"):
                default_index = index
                break
        self.version_combo.setCurrentIndex(default_index)
        layout.addWidget(self.version_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("开始下载")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def version_id(self):
        return str(self.version_combo.currentData() or "").strip()


class InstanceSettingsDialog(QDialog):
    def __init__(self, instance_name, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("实例设置 - " + instance_name)
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        row = 0
        form.addWidget(QLabel("模组加载器"), row, 0)
        self.loader_combo = QComboBox()
        for loader_id, label in loader_installer.LOADERS:
            self.loader_combo.addItem(label, loader_id)
        index = self.loader_combo.findData(settings.get("loader") or "")
        self.loader_combo.setCurrentIndex(index if index >= 0 else 0)
        form.addWidget(self.loader_combo, row, 1)
        row += 1
        form.addWidget(QLabel("Java"), row, 0)
        java_row = QHBoxLayout()
        self.java_edit = QLineEdit(settings.get("java_path") or "")
        self.java_edit.setPlaceholderText("留空则使用全局设置")
        java_row.addWidget(self.java_edit, 1)
        browse = QPushButton("选择…")
        browse.clicked.connect(self._browse_java)
        java_row.addWidget(browse)
        form.addLayout(java_row, row, 1)
        row += 1
        form.addWidget(QLabel("内存"), row, 0)
        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(0, 16384)
        self.memory_spin.setSingleStep(512)
        self.memory_spin.setSuffix(" MB")
        self.memory_spin.setSpecialValueText("跟随全局")
        self.memory_spin.setValue(int(settings.get("max_memory_mb") or 0))
        form.addWidget(self.memory_spin, row, 1)
        row += 1
        form.addWidget(QLabel("窗口大小"), row, 0)
        size_row = QHBoxLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 7680)
        self.width_spin.setSpecialValueText("默认")
        self.width_spin.setValue(int(settings.get("width") or 0))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 4320)
        self.height_spin.setSpecialValueText("默认")
        self.height_spin.setValue(int(settings.get("height") or 0))
        size_row.addWidget(self.width_spin)
        size_row.addWidget(QLabel("×"))
        size_row.addWidget(self.height_spin)
        size_row.addStretch(1)
        form.addLayout(size_row, row, 1)
        row += 1
        self.fullscreen_check = QCheckBox("全屏启动")
        self.fullscreen_check.setChecked(bool(settings.get("fullscreen")))
        form.addWidget(self.fullscreen_check, row, 1)
        row += 1
        form.addWidget(QLabel("额外游戏参数"), row, 0)
        self.args_edit = QLineEdit(settings.get("game_args") or "")
        self.args_edit.setPlaceholderText("例如 --demo，多个参数用空格分隔")
        form.addWidget(self.args_edit, row, 1)
        row += 1
        form.addWidget(QLabel("自动进服"), row, 0)
        server_row = QHBoxLayout()
        self.server_edit = QLineEdit(settings.get("server") or "")
        self.server_edit.setPlaceholderText("服务器地址，留空则不自动进入")
        self.port_edit = QLineEdit(settings.get("server_port") or "25565")
        self.port_edit.setMaximumWidth(100)
        server_row.addWidget(self.server_edit, 1)
        server_row.addWidget(QLabel("端口"))
        server_row.addWidget(self.port_edit)
        form.addLayout(server_row, row, 1)
        layout.addLayout(form)
        note = QLabel("这里只影响当前实例；留空或选“跟随全局”时使用设置页里的值。")
        note.setObjectName("Muted")
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_java(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 java.exe", "", "Java (java.exe javaw.exe);;所有文件 (*)")
        if path:
            self.java_edit.setText(path)

    def values(self):
        return {
            "loader": str(self.loader_combo.currentData() or ""),
            "java_path": self.java_edit.text().strip(),
            "max_memory_mb": int(self.memory_spin.value()),
            "width": int(self.width_spin.value()),
            "height": int(self.height_spin.value()),
            "fullscreen": bool(self.fullscreen_check.isChecked()),
            "game_args": self.args_edit.text().strip(),
            "server": self.server_edit.text().strip(),
            "server_port": self.port_edit.text().strip() or "25565",
        }


class SavesDialog(QDialog):
    def __init__(self, instance_name, parent=None):
        super().__init__(parent)
        self.instance_name = instance_name
        self.setWindowTitle("存档管理 — " + instance_name)
        self.setMinimumSize(640, 440)
        layout = QVBoxLayout(self)
        hint = QLabel("备份会保存到数据目录的 backups 文件夹，不会修改原存档。")
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        layout.addWidget(self.status_label)
        row = QHBoxLayout()
        open_btn = QPushButton("打开文件夹")
        open_btn.clicked.connect(self.open_folder)
        row.addWidget(open_btn)
        backup_btn = QPushButton("备份选中")
        backup_btn.setObjectName("PrimaryButton")
        backup_btn.clicked.connect(self.backup_selected)
        row.addWidget(backup_btn)
        import_btn = QPushButton("导入备份")
        import_btn.clicked.connect(self.import_backup)
        row.addWidget(import_btn)
        delete_btn = QPushButton("删除选中")
        delete_btn.setObjectName("DangerButton")
        delete_btn.clicked.connect(self.delete_selected)
        row.addWidget(delete_btn)
        row.addStretch(1)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        saves = save_manager.list_saves(self.instance_name)
        if not saves:
            item = QListWidgetItem("暂无存档，进入游戏创建一个世界后会出现在这里。")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.list_widget.addItem(item)
            return
        for save in saves:
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(save["mtime"]))
            item = QListWidgetItem(f"{save['name']}    ·    最后修改 {stamp}")
            item.setData(Qt.UserRole, save["name"])
            self.list_widget.addItem(item)
        self.list_widget.setCurrentRow(0)

    def current_save(self):
        item = self.list_widget.currentItem()
        return str(item.data(Qt.UserRole) or "") if item else ""

    def open_folder(self):
        path = save_manager.saves_dir(self.instance_name)
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "打开存档文件夹失败", "无法创建目录：\n" + str(exc))
            return
        ok, error = system_open.open_folder(path)
        if not ok:
            QMessageBox.warning(
                self,
                "打开存档文件夹失败",
                "无法用资源管理器打开：\n%s\n\n%s" % (path, error),
            )

    def backup_selected(self):
        name = self.current_save()
        if not name:
            return
        try:
            path = save_manager.backup_save(self.instance_name, name)
        except Exception as exc:
            QMessageBox.warning(self, "备份失败", str(exc))
            return
        self.status_label.setText("备份完成：" + path)
        QMessageBox.information(self, "备份完成", "已备份到：\n" + path)

    def import_backup(self):
        path, _filter = QFileDialog.getOpenFileName(self, "选择存档备份", "", "Zip 备份 (*.zip)")
        if not path:
            return
        try:
            name = save_manager.import_backup(self.instance_name, path)
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        self.status_label.setText("已导入存档：" + name)
        self.refresh()
        QMessageBox.information(self, "导入完成", "已导入存档：" + name)

    def delete_selected(self):
        name = self.current_save()
        if not name:
            return
        answer = QMessageBox.question(
            self,
            "删除存档",
            f"确定删除存档“{name}”吗？删除后无法恢复，建议先备份。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            save_manager.delete_save(self.instance_name, name)
        except Exception as exc:
            QMessageBox.warning(self, "删除失败", str(exc))
            return
        self.status_label.setText("已删除存档：" + name)
        self.refresh()


class InstancePage(QWidget):
    instance_changed = Signal(str)

    def __init__(self, settings, host, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.host = host
        self._loading = True
        self._installing = False
        self._cached_versions = []
        self._workers = []
        self._versions_loading = False
        self._versions_loaded = False
        self._build_ui()
        self.reload(self.settings.get("last_instance") or "")

    def showEvent(self, event):
        super().showEvent(event)
        if not self._versions_loaded and not self._versions_loading:
            self._load_versions()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("游戏实例")
        title.setStyleSheet("font-size: 17pt; font-weight: 700;")
        layout.addWidget(title)
        self.version_hint = QLabel("正在获取版本列表…")
        self.version_hint.setObjectName("Muted")
        layout.addWidget(self.version_hint)
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selection)
        layout.addWidget(self.list_widget, 1)
        row = QHBoxLayout()
        self.new_btn = QPushButton("新建实例")
        self.new_btn.setObjectName("PrimaryButton")
        self.new_btn.setIcon(create_nav_icon("instance"))
        self.new_btn.clicked.connect(self.new_instance)
        row.addWidget(self.new_btn)
        self.download_btn = QPushButton("下载游戏版本")
        self.download_btn.setIcon(create_nav_icon("modpack"))
        self.download_btn.clicked.connect(self.download_version)
        row.addWidget(self.download_btn)
        self.delete_btn = QPushButton("删除实例")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self.delete_instance)
        row.addWidget(self.delete_btn)
        self.backup_btn = QPushButton("备份存档")
        self.backup_btn.clicked.connect(self.backup_saves)
        row.addWidget(self.backup_btn)
        layout.addLayout(row)
        row2 = QHBoxLayout()
        self.open_btn = QPushButton("打开文件夹")
        self.open_btn.clicked.connect(self.open_folder)
        row2.addWidget(self.open_btn)
        self.import_btn = QPushButton("导入整合包")
        self.import_btn.clicked.connect(lambda: self.host.switch_tab(4))
        row2.addWidget(self.import_btn)
        self.settings_btn = QPushButton("实例设置")
        self.settings_btn.setIcon(create_nav_icon("settings"))
        self.settings_btn.clicked.connect(self.edit_instance)
        row2.addWidget(self.settings_btn)
        self.saves_btn = QPushButton("存档管理")
        self.saves_btn.clicked.connect(self.manage_saves)
        row2.addWidget(self.saves_btn)
        self.retry_versions_btn = QPushButton("重试版本列表")
        self.retry_versions_btn.clicked.connect(self._load_versions)
        row2.addWidget(self.retry_versions_btn)
        row2.addStretch(1)
        layout.addLayout(row2)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress, 1)
        self.stop_btn = QPushButton("停止下载")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.cancel_install)
        progress_row.addWidget(self.stop_btn)
        layout.addLayout(progress_row)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        layout.addWidget(self.status_label)

    def _load_versions(self):
        self._versions_loading = True
        self.retry_versions_btn.setEnabled(False)
        self.version_hint.setText("正在获取版本列表…")
        task = worker.VersionListWorker(self)
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        task.finished_ok.connect(self._on_versions)
        task.finished_error.connect(self._on_versions_error)
        task.start()

    def _on_versions(self, versions):
        self.retry_versions_btn.setEnabled(True)
        self._versions_loading = False
        self._versions_loaded = True
        if isinstance(versions, list):
            self._cached_versions = versions
        releases = len([item for item in self._cached_versions if item.get("type") == "release"])
        if self._cached_versions:
            self.version_hint.setText(
                f"已获取 {len(self._cached_versions)} 个版本（{releases} 个正式版）。点击“新建实例”即可选择。"
            )
        else:
            self.version_hint.setText("没有获取到版本列表。检查网络后点“重试版本列表”。")

    def _on_versions_error(self, _message):
        self.retry_versions_btn.setEnabled(True)
        self._versions_loading = False
        self.version_hint.setText("版本列表加载失败。检查网络后点“重试版本列表”。")

    def reload(self, select=None):
        self._loading = True
        self.list_widget.clear()
        instances = launcher_core.list_instances()
        target = select or self.settings.get("last_instance") or ""
        selected_item = None
        for instance in instances:
            item = QListWidgetItem(
                f"{instance['name']}\n{instance['version_id'] or '未选择版本'} · "
                f"{instance['mods']} 个模组 · {instance['saves']} 个存档"
            )
            item.setIcon(create_nav_icon("instance"))
            item.setData(Qt.UserRole, instance["name"])
            self.list_widget.addItem(item)
            if instance["name"] == target:
                selected_item = item
        if not instances:
            placeholder = QListWidgetItem("还没有实例。点击下方“新建实例”，只需要选择版本即可。")
            placeholder.setFlags(Qt.NoItemFlags)
            self.list_widget.addItem(placeholder)
        elif selected_item is None:
            selected_item = self.list_widget.item(0)
        if selected_item is not None:
            self.list_widget.setCurrentItem(selected_item)
        self._loading = False

    def current_name(self):
        item = self.list_widget.currentItem()
        if not item:
            return ""
        return str(item.data(Qt.UserRole) or "")

    def _on_selection(self, *_args):
        if self._loading:
            return
        name = self.current_name()
        if not name:
            return
        self.settings.set("last_instance", name)
        instance = launcher_core.get_instance(name)
        if instance:
            self.settings.set("last_version_id", instance.get("version_id") or "")
        self.settings.save()
        self.instance_changed.emit(name)

    def _version_entries(self):
        entries = []
        seen = set()
        for version_id in launcher_core.installed_versions():
            entries.append({"id": version_id, "type": "release", "installed": True})
            seen.add(version_id)
        for item in self._cached_versions:
            version_id = str(item.get("id") or "")
            if not version_id or version_id in seen:
                continue
            entries.append(
                {"id": version_id, "type": item.get("type") or "release", "installed": False}
            )
            seen.add(version_id)
        return entries

    def new_instance(self):
        versions = self._version_entries()
        if not versions:
            QMessageBox.information(
                self,
                "还没有版本列表",
                "正在获取版本列表，请稍等几秒后再点“新建实例”。\n如果一直失败，请检查网络后点“重试版本列表”。",
            )
            self._load_versions()
            return
        dialog = NewInstanceDialog(versions, self)
        if dialog.exec() != QDialog.Accepted:
            return
        name, version_id, loader_id = dialog.values()
        if not version_id:
            QMessageBox.warning(self, "创建失败", "请选择一个游戏版本。")
            return
        try:
            launcher_core.create_instance(name, version_id, loader_id)
        except Exception as exc:
            QMessageBox.warning(self, "创建失败", str(exc))
            return
        self.reload(name)
        self.instance_changed.emit(name)
        if self.host:
            self.host.reload_instances(name)
            self.host.log(
                f"已创建实例：{name}（{version_id}，{loader_installer.loader_label(loader_id)}）"
            )
        self.status_label.setText(
            "实例已创建。点击主页的“启动游戏”就会自动下载游戏文件和加载器。"
        )

    def edit_instance(self):
        name = self.current_name()
        if not name:
            QMessageBox.information(self, "实例设置", "请先选择一个实例。")
            return
        current = launcher_core.get_instance_settings(name)
        dialog = InstanceSettingsDialog(name, current, self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        loader_changed = values.get("loader") != (current.get("loader") or "")
        if loader_changed:
            values["loader_version"] = ""
            values["loader_version_id"] = ""
        try:
            launcher_core.update_instance_settings(name, values)
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self.status_label.setText("实例设置已保存。下次启动会按新设置执行。")
        if self.host:
            self.host.log("已更新实例设置：" + name)
        self.reload(name)

    def manage_saves(self):
        name = self.current_name()
        if not name:
            QMessageBox.information(self, "存档管理", "请先选择一个实例。")
            return
        SavesDialog(name, self).exec()

    def download_version(self):
        if self._installing:
            QMessageBox.information(self, "下载中", "已经有一个版本正在下载，请稍候。")
            return
        versions = self._version_entries()
        if not versions:
            QMessageBox.information(
                self,
                "暂时无法下载",
                "还没有获取到版本列表。请检查网络后点“重试版本列表”。",
            )
            self._load_versions()
            return
        dialog = VersionPickerDialog(versions, self)
        if dialog.exec() != QDialog.Accepted:
            return
        version_id = dialog.version_id()
        if version_id:
            self._start_install(version_id)

    def _start_install(self, version_id):
        self._installing = True
        self.new_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.stop_btn.setVisible(True)
        self.status_label.setText("正在下载游戏版本 " + version_id + "，请稍候…")
        task = worker.InstallWorker(
            version_id, self, source=self.settings.get("download_source") or "auto"
        )
        self._install_task = task
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        task.progress.connect(self._on_install_progress)
        task.status_changed.connect(self.status_label.setText)
        task.finished_ok.connect(lambda _result: self._on_install_done(version_id))
        task.finished_error.connect(self._on_install_error)
        task.start()

    def cancel_install(self):
        task = getattr(self, "_install_task", None)
        if task is not None:
            task.cancel()
            self.status_label.setText("正在停止下载…")

    def _on_install_progress(self, done, total):
        if total <= 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, total)
            self.progress.setValue(done)

    def _on_install_done(self, version_id):
        self._installing = False
        self._install_task = None
        self.new_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.stop_btn.setVisible(False)
        self.status_label.setText("版本 " + version_id + " 下载完成，可以新建实例或启动游戏了。")
        QMessageBox.information(
            self,
            "下载完成",
            f"游戏版本 {version_id} 已经下载完成。\n现在新建实例时可以直接选择它。",
        )

    def _on_install_error(self, message):
        self._installing = False
        self._install_task = None
        self.new_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.stop_btn.setVisible(False)
        self.status_label.setText("下载失败：" + str(message))
        QMessageBox.warning(
            self,
            "下载失败",
            str(message) + "\n\n可以检查网络后重试，或换一个版本。",
        )

    def delete_instance(self):
        name = self.current_name()
        if not name:
            QMessageBox.information(self, "删除实例", "当前没有可删除的实例。")
            return
        answer = QMessageBox.question(
            self,
            "删除实例",
            f"确定删除实例“{name}”吗？里面的模组和存档都会一起删除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            launcher_core.delete_instance(name)
        except Exception as exc:
            QMessageBox.warning(self, "删除失败", str(exc))
            return
        if self.host:
            self.host.reload_instances("")
            self.host.log("已删除实例：" + name)
        self.status_label.setText("已删除实例：" + name)

    def backup_saves(self):
        name = self.current_name()
        if not name:
            QMessageBox.information(self, "备份存档", "请先选择一个实例。")
            return
        self.backup_btn.setEnabled(False)
        self.status_label.setText("正在备份存档")
        task = worker.SaveBackupWorker(name, self)
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        task.progress.connect(lambda done, total: self.status_label.setText(f"正在备份 {done}/{total}"))
        task.finished_ok.connect(self._on_backup_done)
        task.finished_error.connect(self._on_backup_error)
        task.start()

    def _on_backup_done(self, result):
        self.backup_btn.setEnabled(True)
        path = result.get("path") if isinstance(result, dict) else str(result)
        self.status_label.setText("备份完成：" + str(path))
        QMessageBox.information(self, "备份完成", "存档已备份到：\n" + str(path))

    def _on_backup_error(self, message):
        self.backup_btn.setEnabled(True)
        self.status_label.setText("备份失败：" + str(message))

    def open_folder(self):
        name = self.current_name()
        if not name:
            return
        path = launcher_core.instance_path(name)
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "打开实例文件夹失败", "无法创建目录：\n" + str(exc))
            return
        ok, error = system_open.open_folder(path)
        if not ok:
            QMessageBox.warning(
                self,
                "打开实例文件夹失败",
                "无法用资源管理器打开：\n%s\n\n%s" % (path, error),
            )

    def save_to_settings(self):
        name = self.current_name()
        if name:
            self.settings.set("last_instance", name)
            instance = launcher_core.get_instance(name)
            if instance:
                self.settings.set("last_version_id", instance.get("version_id") or "")
