import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import launcher_core, worker


class ModpackPage(QWidget):
    def __init__(self, settings, host, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.host = host
        self._workers = []
        self._busy = False
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("整合包导入")
        title.setStyleSheet("font-size: 17pt; font-weight: 700;")
        layout.addWidget(title)

        self.drop_frame = QFrame()
        self.drop_frame.setObjectName("Card")
        drop_layout = QVBoxLayout(self.drop_frame)
        drop_layout.setContentsMargins(20, 28, 20, 28)
        drop_label = QLabel("将整合包文件拖拽到这里")
        drop_label.setAlignment(Qt.AlignCenter)
        drop_label.setStyleSheet("font-size: 14pt; font-weight: 700;")
        drop_layout.addWidget(drop_label)
        hint = QLabel("支持 Modrinth (.mrpack)、CurseForge (.zip)、MultiMC 与 .minecraft 结构")
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(hint)
        layout.addWidget(self.drop_frame)

        row = QHBoxLayout()
        row.addStretch(1)
        self.choose_btn = QPushButton("选择整合包文件")
        self.choose_btn.setObjectName("PrimaryButton")
        self.choose_btn.clicked.connect(self.choose_file)
        row.addWidget(self.choose_btn)
        row.addStretch(1)
        layout.addLayout(row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress, 1)
        self.stop_btn = QPushButton("停止导入")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.stop_install)
        progress_row.addWidget(self.stop_btn)
        layout.addLayout(progress_row)
        self.status_label = QLabel("等待导入")
        self.status_label.setObjectName("Muted")
        layout.addWidget(self.status_label)

        missing_group = QLabel("缺失文件")
        missing_group.setStyleSheet("font-weight: 700;")
        layout.addWidget(missing_group)
        self.missing_list = QListWidget()
        layout.addWidget(self.missing_list, 1)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setObjectName("Muted")
        layout.addWidget(self.detail_label)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile().lower()
                if path.endswith(".mrpack") or path.endswith(".zip"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".mrpack", ".zip")):
                self.handle_pack(path)
                event.acceptProposedAction()
                return
        event.ignore()

    def choose_file(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, "选择整合包", "", "整合包 (*.mrpack *.zip);;所有文件 (*.*)"
        )
        if path:
            self.handle_pack(path)

    def handle_pack(self, path):
        if self._busy:
            QMessageBox.information(self, "导入整合包", "已有导入任务正在进行。")
            return
        if not os.path.isfile(path):
            QMessageBox.warning(self, "导入整合包", "文件不存在。")
            return
        box = QMessageBox(self)
        box.setWindowTitle("导入整合包")
        box.setText("请选择导入方式：")
        new_button = box.addButton("新建实例", QMessageBox.AcceptRole)
        overwrite_button = box.addButton("覆盖当前实例", QMessageBox.DestructiveRole)
        box.addButton("取消", QMessageBox.RejectRole)
        if not self.host.current_instance_name():
            overwrite_button.setEnabled(False)
        box.exec()
        clicked = box.clickedButton()
        if clicked is new_button:
            from PySide6.QtWidgets import QInputDialog

            default_name = os.path.splitext(os.path.basename(path))[0] or "整合包实例"
            name, ok = QInputDialog.getText(self, "新建实例", "实例名称：", text=default_name)
            if not ok:
                return
            if not name.strip():
                QMessageBox.warning(self, "导入整合包", "实例名称不能为空。")
                return
            self.start_install(path, name.strip(), False)
        elif clicked is overwrite_button:
            current = self.host.current_instance_name()
            answer = QMessageBox.question(
                self,
                "覆盖实例",
                f"确定用该整合包覆盖实例“{current}”吗？现有 Mod 与配置会被替换。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                self.start_install(path, current, True)

    def start_install(self, path, instance_name, overwrite):
        self._busy = True
        self.choose_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.stop_btn.setVisible(True)
        self.missing_list.clear()
        self.detail_label.setText("")
        self.status_label.setText("正在导入整合包…")
        task = worker.ModpackInstallWorker(path, instance_name, overwrite, self)
        self._install_task = task
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        task.progress.connect(self._on_progress)
        task.status_changed.connect(self.status_label.setText)
        task.finished_ok.connect(self._on_installed)
        task.finished_error.connect(self._on_error)
        task.start()

    def _on_progress(self, done, total):
        if total <= 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, total)
            self.progress.setValue(done)

    def _on_installed(self, result):
        self._busy = False
        self._install_task = None
        self.choose_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.stop_btn.setVisible(False)
        missing = result.get("missing_mods") or []
        for item in missing:
            self.missing_list.addItem(str(item))
        self.status_label.setText("整合包导入完成")
        details = []
        if result.get("actions"):
            details.append("已完成：" + "；".join(result["actions"]))
        if result.get("warnings"):
            details.append("警告：" + "；".join(result["warnings"]))
        self.detail_label.setText("\n".join(details))
        if self.host:
            self.host.reload_instances(result.get("instance") or "")
            self.host.log(f"整合包导入完成：{result.get('instance')}（{len(missing)} 个缺失文件）")
        QMessageBox.information(
            self,
            "导入完成",
            f"实例“{result.get('instance')}”已导入。\n缺失文件：{len(missing)} 个",
        )

    def _on_error(self, message):
        self._busy = False
        self._install_task = None
        self.choose_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.stop_btn.setVisible(False)
        self.status_label.setText("导入失败：" + str(message))
        QMessageBox.warning(self, "导入失败", str(message))

    def stop_install(self):
        task = getattr(self, "_install_task", None)
        if task is not None:
            task.cancel()
            self.status_label.setText("正在停止导入…")

    def save_to_settings(self):
        return
