import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import launcher_core, system_open, worker


class ResourceDownloadDialog(QDialog):
    def __init__(self, project_type, target_dir, game_version="", parent=None):
        super().__init__(parent)
        self.project_type = project_type
        self.target_dir = target_dir
        self.game_version = game_version
        self._hits = []
        self._workers = []
        self.setWindowTitle("下载资源包" if project_type == "resourcepack" else "下载光影")
        self.setMinimumSize(640, 460)
        layout = QVBoxLayout(self)
        hint = QLabel("从 Modrinth 搜索并下载到当前实例，不需要打开浏览器。")
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入名称，例如 Faithful、BSL")
        self.search_edit.returnPressed.connect(self.search)
        search_row.addWidget(self.search_edit, 1)
        self.search_btn = QPushButton("搜索")
        self.search_btn.setObjectName("PrimaryButton")
        self.search_btn.clicked.connect(self.search)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)
        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(lambda _item: self.download())
        layout.addWidget(self.results, 1)
        self.status_label = QLabel("输入关键词后点搜索")
        self.status_label.setObjectName("Muted")
        layout.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.download_btn = QPushButton("下载选中项")
        self.download_btn.setObjectName("PrimaryButton")
        self.download_btn.clicked.connect(self.download)
        bottom.addWidget(self.download_btn)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def search(self):
        query = self.search_edit.text().strip()
        if not query:
            self.status_label.setText("先输入要搜索的名称")
            return
        self.search_btn.setEnabled(False)
        self.status_label.setText("正在搜索…")
        task = worker.ModSearchWorker(query, 20, self.project_type, self)
        self._workers.append(task)
        task.finished_ok.connect(self._on_results)
        task.finished_error.connect(self._on_error)
        task.finished.connect(lambda: self.search_btn.setEnabled(True))
        task.start()

    def _on_results(self, hits):
        self._hits = hits if isinstance(hits, list) else []
        self.results.clear()
        if not self._hits:
            self.status_label.setText("没有找到结果，换个关键词试试")
            return
        for hit in self._hits:
            title = str(hit.get("title") or hit.get("slug") or "")
            downloads = int(hit.get("downloads") or 0)
            item = QListWidgetItem(f"{title}   ·   {downloads:,} 次下载")
            item.setData(Qt.UserRole, str(hit.get("project_id") or hit.get("slug") or ""))
            item.setToolTip(str(hit.get("description") or ""))
            self.results.addItem(item)
        self.results.setCurrentRow(0)
        self.status_label.setText(f"找到 {len(self._hits)} 个结果，双击或点下方按钮下载")

    def download(self):
        item = self.results.currentItem()
        if not item:
            self.status_label.setText("先选择一个结果")
            return
        project_id = str(item.data(Qt.UserRole) or "")
        if not project_id:
            return
        self.download_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("正在下载…")
        task = worker.ModDownloadWorker(project_id, self.game_version, self.target_dir, parent=self)
        self._workers.append(task)
        task.progress.connect(self._on_progress)
        task.finished_ok.connect(self._on_downloaded)
        task.finished_error.connect(self._on_error)
        task.start()

    def _on_progress(self, done, total):
        if total <= 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, total)
            self.progress.setValue(done)

    def _on_downloaded(self, result):
        self.download_btn.setEnabled(True)
        self.progress.setVisible(False)
        name = result.get("name") if isinstance(result, dict) else ""
        self.status_label.setText("下载完成：" + str(name or ""))

    def _on_error(self, message):
        self.download_btn.setEnabled(True)
        self.search_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.status_label.setText("失败：" + str(message))
        QMessageBox.warning(self, "操作失败", str(message))


class ResourcePage(QWidget):
    def __init__(self, settings, host, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.host = host
        self._instance = ""
        self._build_ui()
        self.on_instance_changed(self.host.current_instance_name() if self.host else "")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("资源管理")
        title.setStyleSheet("font-size: 17pt; font-weight: 700;")
        layout.addWidget(title)
        self.instance_label = QLabel("未选择实例")
        self.instance_label.setObjectName("Muted")
        layout.addWidget(self.instance_label)

        self.resource_group = self._make_group("资源包 resourcepacks", "resourcepack")
        self.shader_group = self._make_group("光影 shaderpacks", "shader")
        layout.addWidget(self.resource_group[0], 1)
        layout.addWidget(self.shader_group[0], 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        layout.addWidget(self.status_label)
        self.refresh()

    def _make_group(self, title, project_type):
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        list_widget = QListWidget()
        group_layout.addWidget(list_widget, 1)
        row = QHBoxLayout()
        download_btn = QPushButton("下载资源")
        download_btn.setObjectName("PrimaryButton")
        download_btn.clicked.connect(lambda: self._open_download(project_type))
        row.addWidget(download_btn)
        row.addStretch(1)
        open_btn = QPushButton("打开文件夹")
        open_btn.clicked.connect(lambda: self._open_folder(project_type))
        row.addWidget(open_btn)
        group_layout.addLayout(row)
        return group, list_widget

    def _open_download(self, project_type):
        if not self._instance:
            QMessageBox.information(self, "下载资源", "请先在主页或实例页选择一个实例。")
            return
        sub = "resourcepacks" if project_type == "resourcepack" else "shaderpacks"
        target = os.path.join(launcher_core.instance_path(self._instance), sub)
        os.makedirs(target, exist_ok=True)
        game_version = launcher_core.instance_game_version(self._instance)
        dialog = ResourceDownloadDialog(project_type, target, game_version, self)
        dialog.exec()
        self.refresh()

    def _open_folder(self, project_type):
        if not self._instance:
            return
        sub = "resourcepacks" if project_type == "resourcepack" else "shaderpacks"
        path = os.path.join(launcher_core.instance_path(self._instance), sub)
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "打开文件夹失败", "无法创建目录：\n" + str(exc))
            return
        ok, error = system_open.open_folder(path)
        if not ok:
            QMessageBox.warning(
                self,
                "打开文件夹失败",
                "无法用资源管理器打开：\n%s\n\n%s" % (path, error),
            )

    def on_instance_changed(self, name):
        self._instance = name or ""
        instance = launcher_core.get_instance(self._instance) if self._instance else None
        if instance:
            self.instance_label.setText("当前实例：" + instance["name"])
        else:
            self.instance_label.setText("未选择实例")
        self.refresh()

    def _fill(self, list_widget, directory):
        list_widget.clear()
        if not self._instance:
            list_widget.addItem("暂无")
            return
        path = os.path.join(launcher_core.instance_path(self._instance), directory)
        try:
            names = sorted(
                name
                for name in os.listdir(path)
                if os.path.isfile(os.path.join(path, name)) and name.lower().endswith((".zip", ".jar"))
            )
        except Exception:
            names = []
        if not names:
            list_widget.addItem("暂无")
            return
        for name in names:
            list_widget.addItem(name)

    def refresh(self):
        self._fill(self.resource_group[1], "resourcepacks")
        self._fill(self.shader_group[1], "shaderpacks")

    def save_to_settings(self):
        return
