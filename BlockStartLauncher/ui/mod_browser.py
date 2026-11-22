import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core import launcher_core, mod_manager, system_open, worker
from core.icon_factory import create_nav_icon


class ModBrowserPage(QWidget):
    def __init__(self, settings, host, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.host = host
        self._workers = []
        self._loading = True
        self._instance = ""
        self._current_project = ""
        self._current_hit = {}
        self._download_task = None
        self._build_ui()
        self.on_instance_changed(self.host.current_instance_name() if self.host else "")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("模组")
        title.setStyleSheet("font-size: 17pt; font-weight: 700;")
        header.addWidget(title)
        header.addStretch(1)
        self.instance_label = QLabel("未选择实例")
        self.instance_label.setObjectName("Muted")
        header.addWidget(self.instance_label)
        layout.addLayout(header)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索模组，例如 sodium、jei、小地图")
        self.search_edit.returnPressed.connect(self.search)
        search_row.addWidget(self.search_edit, 1)
        self.search_btn = QPushButton("搜索")
        self.search_btn.setObjectName("PrimaryButton")
        self.search_btn.clicked.connect(self.search)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_browse_page())
        self.stack.addWidget(self._build_detail_page())
        layout.addWidget(self.stack, 1)

    def _build_browse_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        result_hint = QLabel("搜索结果（点击任意一项查看模组介绍并在应用内下载）")
        result_hint.setObjectName("Muted")
        layout.addWidget(result_hint)
        self.results_list = QListWidget()
        self.results_list.setIconSize(QSize(26, 26))
        self.results_list.itemClicked.connect(self.open_detail)
        layout.addWidget(self.results_list, 1)

        installed_group = QGroupBox("已安装的模组（勾选=启用，取消勾选=禁用）")
        installed_layout = QVBoxLayout(installed_group)
        self.mods_list = QListWidget()
        self.mods_list.setIconSize(QSize(24, 24))
        self.mods_list.itemChanged.connect(self._on_mod_toggled)
        installed_layout.addWidget(self.mods_list, 1)
        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #F59E0B;")
        installed_layout.addWidget(self.warning_label)
        buttons = QHBoxLayout()
        self.enable_btn = QPushButton("启用 / 禁用选中")
        self.enable_btn.clicked.connect(self.toggle_selected)
        buttons.addWidget(self.enable_btn)
        self.delete_btn = QPushButton("删除选中模组")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self.delete_selected)
        buttons.addWidget(self.delete_btn)
        self.folder_btn = QPushButton("打开模组文件夹")
        self.folder_btn.clicked.connect(self.open_mods_folder)
        buttons.addWidget(self.folder_btn)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_mods)
        buttons.addWidget(self.refresh_btn)
        buttons.addStretch(1)
        installed_layout.addLayout(buttons)
        layout.addWidget(installed_group, 1)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        layout.addWidget(self.status_label)
        return page

    def _build_detail_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        top = QHBoxLayout()
        self.back_btn = QPushButton("← 返回搜索结果")
        self.back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        top.addWidget(self.back_btn)
        top.addStretch(1)
        layout.addLayout(top)

        header = QHBoxLayout()
        self.detail_icon = QLabel()
        self.detail_icon.setMinimumSize(76, 76)
        self.detail_icon.setMaximumSize(76, 76)
        self.detail_icon.setScaledContents(True)
        self.detail_icon.setPixmap(create_nav_icon("mod").pixmap(72, 72))
        header.addWidget(self.detail_icon)
        text_layout = QVBoxLayout()
        self.detail_title = QLabel("模组介绍")
        self.detail_title.setStyleSheet("font-size: 18pt; font-weight: 700;")
        self.detail_title.setWordWrap(True)
        text_layout.addWidget(self.detail_title)
        self.detail_meta = QLabel("")
        self.detail_meta.setObjectName("Muted")
        self.detail_meta.setWordWrap(True)
        text_layout.addWidget(self.detail_meta)
        header.addLayout(text_layout, 1)
        layout.addLayout(header)

        self.detail_body = QTextBrowser()
        self.detail_body.setOpenExternalLinks(False)
        self.detail_body.setOpenLinks(False)
        self.detail_body.setPlainText("正在加载模组介绍…")
        layout.addWidget(self.detail_body, 1)

        download_row = QHBoxLayout()
        download_row.addWidget(QLabel("选择版本"))
        self.version_combo = QComboBox()
        download_row.addWidget(self.version_combo, 1)
        self.download_btn = QPushButton("下载到当前实例")
        self.download_btn.setObjectName("PrimaryButton")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self.download_selected_version)
        download_row.addWidget(self.download_btn)
        self.stop_btn = QPushButton("停止下载")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.stop_download)
        download_row.addWidget(self.stop_btn)
        layout.addLayout(download_row)
        self.detail_progress = QProgressBar()
        self.detail_progress.setVisible(False)
        layout.addWidget(self.detail_progress)
        self.detail_status = QLabel("")
        self.detail_status.setObjectName("Muted")
        self.detail_status.setWordWrap(True)
        layout.addWidget(self.detail_status)
        return page

    def on_instance_changed(self, name):
        self._instance = name or ""
        instance = launcher_core.get_instance(self._instance) if self._instance else None
        if instance:
            self.instance_label.setText(
                "当前实例：" + instance["name"] + "（" + (instance.get("version_id") or "未选择版本") + "）"
            )
        else:
            self.instance_label.setText("未选择实例，请先创建实例")
        self.load_mods()

    def _track(self, task):
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        return task

    def search(self):
        query = self.search_edit.text().strip()
        if not query:
            return
        self.search_btn.setEnabled(False)
        self.status_label.setText("正在搜索…")
        task = self._track(worker.ModSearchWorker(query, 20, "mod", self))
        task.finished_ok.connect(self._on_search_results)
        task.finished_error.connect(self._on_search_error)
        task.start()

    def _on_search_results(self, hits):
        self.search_btn.setEnabled(True)
        self.results_list.clear()
        for hit in hits or []:
            project_id = hit.get("project_id") or hit.get("slug") or ""
            if not project_id:
                continue
            title = str(hit.get("title") or project_id)
            description = str(hit.get("description") or "").strip()
            item = QListWidgetItem(f"{title}\n{description[:100]}")
            item.setIcon(create_nav_icon("mod"))
            item.setData(Qt.UserRole, hit)
            item.setToolTip("点击查看介绍并下载")
            self.results_list.addItem(item)
        self.status_label.setText(f"找到 {self.results_list.count()} 个模组，点击查看介绍")
        if self.results_list.count():
            self.stack.setCurrentIndex(0)

    def _on_search_error(self, message):
        self.search_btn.setEnabled(True)
        self.status_label.setText("搜索失败：" + str(message))

    def open_detail(self, item):
        hit = item.data(Qt.UserRole) or {}
        project_id = str(hit.get("project_id") or hit.get("slug") or "")
        if not project_id:
            return
        self._current_project = project_id
        self._current_hit = hit
        self.detail_title.setText(str(hit.get("title") or project_id))
        downloads = hit.get("downloads")
        self.detail_meta.setText(
            ("下载 " + f"{downloads:,}" if isinstance(downloads, int) else "")
            + (" · " + str(hit.get("author")) if hit.get("author") else "")
        )
        self.detail_body.setPlainText(
            str(hit.get("description") or "") + "\n\n正在加载完整介绍…"
        )
        self.detail_icon.setPixmap(create_nav_icon("mod").pixmap(72, 72))
        self.version_combo.clear()
        self.download_btn.setEnabled(False)
        self.detail_status.setText("正在加载…")
        self.stack.setCurrentIndex(1)
        task = self._track(worker.ModDetailsWorker(project_id, self))
        task.finished_ok.connect(self._on_details)
        task.finished_error.connect(self._on_details_error)
        task.start()

    def _on_details(self, data):
        project = data.get("project") or {}
        versions = data.get("versions") or []
        title = str(project.get("title") or self._current_hit.get("title") or "模组介绍")
        description = str(project.get("description") or "")
        body = str(project.get("body") or "")
        downloads = project.get("downloads")
        meta_parts = []
        if isinstance(downloads, int):
            meta_parts.append(f"下载 {downloads:,}")
        if project.get("followers"):
            meta_parts.append(f"关注 {project['followers']:,}")
        categories = project.get("categories") or []
        if categories:
            meta_parts.append("分类：" + "、".join(str(item) for item in categories[:4]))
        self.detail_title.setText(title)
        self.detail_meta.setText(" · ".join(meta_parts) or description)
        text = body if body else description
        if len(text) > 12000:
            text = text[:12000] + "\n\n（介绍太长，后面省略）"
        self.detail_body.setPlainText(text)
        icon = data.get("icon") or b""
        if icon:
            pixmap = QPixmap()
            if pixmap.loadFromData(icon):
                self.detail_icon.setPixmap(
                    pixmap.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        self.version_combo.clear()
        for version in versions:
            game_versions = version.get("game_versions") or []
            loaders = version.get("loaders") or []
            label = str(version.get("version_number") or version.get("name") or "版本")
            if game_versions:
                label += " · " + "/".join(str(item) for item in game_versions[:3])
            if loaders:
                label += " · " + "/".join(str(item) for item in loaders[:2])
            self.version_combo.addItem(label, version.get("id"))
        if self.version_combo.count():
            game_version = ""
            instance = launcher_core.get_instance(self._instance) if self._instance else None
            if instance:
                game_version = instance.get("version_id") or ""
            if game_version:
                for index, version in enumerate(versions):
                    if game_version in (version.get("game_versions") or []):
                        self.version_combo.setCurrentIndex(index)
                        break
            self.download_btn.setEnabled(bool(self._instance))
            self.detail_status.setText(f"共 {self.version_combo.count()} 个可用版本，选择后点“下载到当前实例”。")
        else:
            self.detail_status.setText("这个模组没有可下载的版本。")
        if not self._instance:
            self.detail_status.setText("请先在“游戏实例”里选择一个实例，再下载模组。")

    def _on_details_error(self, message):
        self.detail_status.setText("介绍加载失败：" + str(message))
        self.detail_body.setPlainText(str(self._current_hit.get("description") or ""))

    def download_selected_version(self):
        if not self._instance:
            QMessageBox.information(self, "下载模组", "请先在“游戏实例”里选择一个实例。")
            return
        if not self._current_project:
            return
        version_id = str(self.version_combo.currentData() or "")
        if not version_id:
            QMessageBox.information(self, "下载模组", "请先选择要下载的版本。")
            return
        instance = launcher_core.get_instance(self._instance)
        if not instance:
            QMessageBox.warning(self, "下载模组", "当前实例不存在。")
            return
        target = os.path.join(instance["path"], "mods")
        self.download_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.detail_progress.setVisible(True)
        self.detail_progress.setRange(0, 0)
        self.detail_status.setText("正在下载，请稍候…")
        task = self._track(
            worker.ModDownloadWorker(
                self._current_project,
                instance.get("version_id") or "",
                target,
                version_id,
                self,
            )
        )
        self._download_task = task
        task.progress.connect(self._on_download_progress)
        task.status_changed.connect(self.detail_status.setText)
        task.finished_ok.connect(self._on_download_ok)
        task.finished_error.connect(self._on_download_error)
        task.start()

    def stop_download(self):
        if self._download_task is not None:
            self._download_task.cancel()
            self.detail_status.setText("正在停止下载…")

    def _on_download_progress(self, done, total):
        if total <= 0:
            self.detail_progress.setRange(0, 0)
        else:
            self.detail_progress.setRange(0, total)
            self.detail_progress.setValue(done)

    def _on_download_ok(self, result):
        self._download_task = None
        self.download_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.detail_progress.setVisible(False)
        self.detail_status.setText("下载完成：" + str(result.get("name") or ""))
        if self.host:
            self.host.log("已下载模组：" + str(result.get("name") or ""))
        self.load_mods()
        QMessageBox.information(
            self, "下载完成", "模组已经放进当前实例的 mods 文件夹，启动游戏即可使用。"
        )

    def _on_download_error(self, message):
        self._download_task = None
        self.download_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.detail_progress.setVisible(False)
        self.detail_status.setText(str(message))

    def load_mods(self):
        self._loading = True
        self.mods_list.clear()
        warnings = []
        if self._instance:
            path = launcher_core.instance_path(self._instance)
            for mod in mod_manager.list_mods(path):
                item = QListWidgetItem(mod["name"])
                item.setIcon(create_nav_icon("mod"))
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if mod["enabled"] else Qt.Unchecked)
                item.setData(Qt.UserRole, mod["path"])
                self.mods_list.addItem(item)
            warnings.extend(mod_manager.detect_loader_conflicts(path))
            for duplicate in mod_manager.detect_duplicate_modids(path):
                warnings.append(f"重复 Mod ID：{duplicate['modid']}（{', '.join(duplicate['files'])}）")
        else:
            placeholder = QListWidgetItem("请先选择一个实例")
            placeholder.setFlags(Qt.NoItemFlags)
            self.mods_list.addItem(placeholder)
        self.warning_label.setText("\n".join(warnings))
        self._loading = False

    def _on_mod_toggled(self, item):
        if self._loading:
            return
        path = item.data(Qt.UserRole)
        if not path:
            return
        checked = item.checkState() == Qt.Checked
        enabled = str(path).lower().endswith(".jar")
        if checked == enabled:
            return
        try:
            mod_manager.toggle_mod(str(path))
            self.status_label.setText(("已启用 " if checked else "已禁用 ") + os.path.basename(str(path)))
        except Exception as exc:
            QMessageBox.warning(self, "修改失败", str(exc))
        self.load_mods()
        if self.host:
            self.host.dashboard.refresh_stats()

    def toggle_selected(self):
        selected = self.mods_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "启用 / 禁用", "请先在列表里选择模组。")
            return
        desired_checked = selected[0].checkState() != Qt.Checked
        errors = []
        for item in selected:
            path = str(item.data(Qt.UserRole) or "")
            if not path:
                continue
            enabled = path.lower().endswith(".jar")
            if enabled != desired_checked:
                try:
                    mod_manager.toggle_mod(path)
                except Exception as exc:
                    errors.append(f"{item.text()}：{exc}")
        self.load_mods()
        if self.host:
            self.host.dashboard.refresh_stats()
        if errors:
            QMessageBox.warning(self, "部分修改失败", "\n".join(errors))

    def delete_selected(self):
        selected = self.mods_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "删除模组", "请先在列表里选择要删除的模组。")
            return
        names = [item.text() for item in selected]
        answer = QMessageBox.question(
            self,
            "删除模组",
            "确定删除这些模组吗？\n\n" + "\n".join(names[:10]),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        errors = []
        for item in selected:
            path = item.data(Qt.UserRole)
            try:
                mod_manager.delete_mod(str(path))
            except Exception as exc:
                errors.append(f"{item.text()}：{exc}")
        self.load_mods()
        if self.host:
            self.host.dashboard.refresh_stats()
        if errors:
            QMessageBox.warning(self, "部分删除失败", "\n".join(errors))
        else:
            self.status_label.setText(f"已删除 {len(names)} 个模组")

    def open_mods_folder(self):
        if not self._instance:
            return
        path = os.path.join(launcher_core.instance_path(self._instance), "mods")
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "打开模组文件夹失败", "无法创建目录：\n" + str(exc))
            return
        ok, error = system_open.open_folder(path)
        if not ok:
            QMessageBox.warning(
                self,
                "打开模组文件夹失败",
                "无法用资源管理器打开：\n%s\n\n%s" % (path, error),
            )

    def save_to_settings(self):
        return
