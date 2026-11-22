import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import launcher_core, worker

STATUS_TEXT = {"ok": "正常", "missing": "缺失", "mismatch": "文件损坏"}
TYPE_TEXT = {"client": "客户端", "library": "库文件", "native": "原生库", "asset": "资源文件"}


class RepairPage(QWidget):
    def __init__(self, settings, host, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.host = host
        self._workers = []
        self._inventory = []
        self._verify_version = ""
        self._loading_table = False
        self._busy = False
        self._diagnosed = False
        self._build_ui()
        self.reload_versions()
        self.load_history()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        title = QLabel("修复与校验")
        title.setStyleSheet("font-size: 17pt; font-weight: 700;")
        layout.addWidget(title)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_minecraft_tab(), "一键修复游戏")
        self.tabs.addTab(self._build_launcher_tab(), "修复启动器")
        self.tabs.addTab(self._build_manual_tab(), "检查游戏文件")
        layout.addWidget(self.tabs, 1)

        history_group = QGroupBox("最近修复记录")
        history_layout = QVBoxLayout(history_group)
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(110)
        history_layout.addWidget(self.history_list)
        layout.addWidget(history_group)

    def _build_minecraft_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(QLabel("版本 / 实例"))
        self.version_combo = QComboBox()
        row.addWidget(self.version_combo, 1)
        layout.addLayout(row)
        buttons = QHBoxLayout()
        self.repair_btn = QPushButton("开始修复")
        self.repair_btn.setObjectName("PrimaryButton")
        self.repair_btn.clicked.connect(lambda: self.start_repair("auto"))
        buttons.addWidget(self.repair_btn)
        self.natives_btn = QPushButton("只修复运行库（进阶）")
        self.natives_btn.clicked.connect(lambda: self.start_repair("natives"))
        buttons.addWidget(self.natives_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.mc_progress = QProgressBar()
        self.mc_progress.setVisible(False)
        layout.addWidget(self.mc_progress)
        self.mc_output = QTextEdit()
        self.mc_output.setReadOnly(True)
        layout.addWidget(self.mc_output, 1)
        return page

    def _build_launcher_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        self.diagnose_btn = QPushButton("诊断启动器")
        self.diagnose_btn.setObjectName("PrimaryButton")
        self.diagnose_btn.clicked.connect(self.diagnose_launcher)
        row.addWidget(self.diagnose_btn)
        self.fix_launcher_btn = QPushButton("执行修复")
        self.fix_launcher_btn.setEnabled(False)
        self.fix_launcher_btn.clicked.connect(self.fix_launcher)
        row.addWidget(self.fix_launcher_btn)
        row.addStretch(1)
        layout.addLayout(row)
        self.checks_list = QListWidget()
        layout.addWidget(self.checks_list, 1)
        self.launcher_output = QTextEdit()
        self.launcher_output.setReadOnly(True)
        self.launcher_output.setMaximumHeight(160)
        layout.addWidget(self.launcher_output)
        return page

    def _build_manual_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(QLabel("版本"))
        self.verify_combo = QComboBox()
        row.addWidget(self.verify_combo, 1)
        self.scan_btn = QPushButton("检查文件")
        self.scan_btn.setObjectName("PrimaryButton")
        self.scan_btn.clicked.connect(self.scan_files)
        row.addWidget(self.scan_btn)
        layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("筛选"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("全部", "all")
        self.filter_combo.addItem("仅异常", "abnormal")
        self.filter_combo.addItem("缺失", "missing")
        self.filter_combo.addItem("文件损坏", "mismatch")
        self.filter_combo.addItem("正常", "ok")
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        row2.addWidget(self.filter_combo)
        self.select_abnormal_btn = QPushButton("选中所有问题文件")
        self.select_abnormal_btn.clicked.connect(self.select_abnormal)
        row2.addWidget(self.select_abnormal_btn)
        self.repair_selected_btn = QPushButton("修复选中的文件")
        self.repair_selected_btn.setObjectName("PrimaryButton")
        self.repair_selected_btn.setEnabled(False)
        self.repair_selected_btn.clicked.connect(self.repair_selected)
        row2.addWidget(self.repair_selected_btn)
        row2.addStretch(1)
        layout.addLayout(row2)

        self.verify_progress = QProgressBar()
        self.verify_progress.setVisible(False)
        layout.addWidget(self.verify_progress)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["类型", "路径", "状态", "勾选"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._on_table_item_changed)
        layout.addWidget(self.table, 1)

        self.verify_status = QLabel("请选择版本后点击“检查文件”")
        self.verify_status.setObjectName("Muted")
        layout.addWidget(self.verify_status)
        return page

    def reload_versions(self):
        keep_repair = self.version_combo.currentData()
        keep_verify = self.verify_combo.currentData()
        entries = []
        seen = set()
        for version_id in launcher_core.installed_versions():
            entries.append((version_id, version_id))
            seen.add(version_id)
        for instance in launcher_core.list_instances():
            version_id = instance.get("version_id") or ""
            if version_id and version_id not in seen:
                entries.append((f"{instance['name']} · {version_id}", version_id))
                seen.add(version_id)
        for combo, keep in ((self.version_combo, keep_repair), (self.verify_combo, keep_verify)):
            combo.blockSignals(True)
            combo.clear()
            if entries:
                for label, version_id in entries:
                    combo.addItem(label, version_id)
            else:
                combo.addItem("暂无可用版本", "")
            if keep:
                index = combo.findData(keep)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def load_history(self):
        self.history_list.clear()
        history = self.settings.get("repair_history") or []
        if not isinstance(history, list):
            history = []
        for record in reversed(history[-20:]):
            if not isinstance(record, dict):
                continue
            timestamp = record.get("ts") or 0
            try:
                when = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(timestamp)))
            except Exception:
                when = ""
            self.history_list.addItem(
                f"{when}  {record.get('version', '')} · {record.get('mode', '')} · {record.get('result', '')}"
            )
        if not history:
            self.history_list.addItem("暂无修复记录")

    def _record_history(self, version, mode, result):
        self.settings.append_repair_history(
            {"version": version, "mode": mode, "result": result, "ts": time.time()}
        )
        self.settings.save()
        self.load_history()

    def _track(self, task):
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        return task

    def start_repair(self, mode):
        version_id = self.version_combo.currentData()
        if not version_id:
            QMessageBox.information(self, "修复 Minecraft", "没有可修复的版本，请先安装或导入实例。")
            return
        self.repair_btn.setEnabled(False)
        self.natives_btn.setEnabled(False)
        self.mc_progress.setVisible(True)
        self.mc_progress.setRange(0, 0)
        self.mc_output.clear()
        self.mc_output.append("开始修复：" + str(version_id) + "（" + mode + "）")
        task = self._track(worker.RepairMinecraftWorker(version_id, mode, parent=self))
        task.progress.connect(self._on_mc_progress)
        task.finished_ok.connect(lambda result: self._on_mc_done(version_id, mode, result))
        task.finished_error.connect(self._on_mc_error)
        task.start()

    def _on_mc_progress(self, done, total):
        if total <= 0:
            self.mc_progress.setRange(0, 0)
        else:
            self.mc_progress.setRange(0, total)
            self.mc_progress.setValue(done)

    def _on_mc_done(self, version_id, mode, result):
        self.repair_btn.setEnabled(True)
        self.natives_btn.setEnabled(True)
        self.mc_progress.setVisible(False)
        for action in result.get("actions") or []:
            self.mc_output.append("[完成] " + str(action))
        for warning in result.get("warnings") or []:
            self.mc_output.append("[警告] " + str(warning))
        for line in result.get("log") or []:
            self.mc_output.append(str(line))
        outcome = "成功" if result.get("repaired") else "未完成"
        self.mc_output.append("结果：" + outcome)
        self._record_history(version_id, mode, outcome)
        if self.host:
            self.host.log(f"Minecraft 修复（{version_id}/{mode}）：{outcome}")

    def _on_mc_error(self, message):
        self.repair_btn.setEnabled(True)
        self.natives_btn.setEnabled(True)
        self.mc_progress.setVisible(False)
        self.mc_output.append("修复失败：" + str(message))
        self._record_history("", "minecraft", "失败")

    def diagnose_launcher(self):
        self.diagnose_btn.setEnabled(False)
        self.fix_launcher_btn.setEnabled(False)
        self.checks_list.clear()
        self.launcher_output.clear()
        self.checks_list.addItem("正在诊断…")
        task = self._track(worker.RepairLauncherWorker(False, self))
        task.diagnoses_ready.connect(self._fill_checks)
        task.status_changed.connect(self.launcher_output.append)
        task.finished_ok.connect(self._on_diagnose_done)
        task.finished_error.connect(self._on_launcher_error)
        task.start()

    def _fill_checks(self, checks):
        self.checks_list.clear()
        for check in checks or []:
            status = check.get("status")
            mark = {"ok": "正常", "missing": "缺失", "corrupt": "损坏"}.get(status, str(status))
            self.checks_list.addItem(
                f"{check.get('name')}：{mark} — {check.get('detail')}"
            )

    def _on_diagnose_done(self, result):
        self.diagnose_btn.setEnabled(True)
        self.fix_launcher_btn.setEnabled(True)
        self._diagnosed = True
        self.launcher_output.append("诊断完成，可执行修复。")

    def fix_launcher(self):
        self.fix_launcher_btn.setEnabled(False)
        self.diagnose_btn.setEnabled(False)
        self.launcher_output.append("正在修复启动器…")
        task = self._track(worker.RepairLauncherWorker(True, self))
        task.diagnoses_ready.connect(self._fill_checks)
        task.status_changed.connect(self.launcher_output.append)
        task.finished_ok.connect(self._on_launcher_fixed)
        task.finished_error.connect(self._on_launcher_error)
        task.start()

    def _on_launcher_fixed(self, result):
        self.fix_launcher_btn.setEnabled(True)
        self.diagnose_btn.setEnabled(True)
        for action in result.get("actions") or []:
            self.launcher_output.append("[完成] " + str(action))
        for preserved in result.get("preserved") or []:
            self.launcher_output.append("[保留] " + str(preserved))
        outcome = "成功" if result.get("repaired") else "无需修复"
        self._record_history("BlockStart Launcher", "launcher", outcome)
        if self.host:
            self.host.log("启动器修复：" + outcome)

    def _on_launcher_error(self, message):
        self.fix_launcher_btn.setEnabled(True)
        self.diagnose_btn.setEnabled(True)
        self.launcher_output.append("操作失败：" + str(message))

    def scan_files(self):
        version_id = self.verify_combo.currentData()
        if not version_id:
            QMessageBox.information(self, "手动校验", "没有可校验的版本。")
            return
        self.scan_btn.setEnabled(False)
        self.repair_selected_btn.setEnabled(False)
        self.verify_progress.setVisible(True)
        self.verify_progress.setRange(0, 0)
        self.verify_status.setText("正在扫描…")
        self.table.setRowCount(0)
        self._inventory = []
        task = self._track(worker.ManualVerifyWorker(version_id, self))
        task.inventory_ready.connect(lambda items: self._on_inventory(version_id, items))
        task.finished_ok.connect(lambda _items: self._on_inventory_done(version_id))
        task.finished_error.connect(self._on_verify_error)
        task.start()

    def _on_inventory(self, version_id, items):
        self._verify_version = version_id
        self._inventory = list(items or [])
        self._loading_table = True
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(self._inventory))
        saved = set(self.settings.get_manual_selection(version_id))
        for row, item in enumerate(self._inventory):
            type_item = QTableWidgetItem(TYPE_TEXT.get(item.get("type"), str(item.get("type"))))
            path_item = QTableWidgetItem(str(item.get("path")))
            path_item.setToolTip(str(item.get("path")))
            status_item = QTableWidgetItem(STATUS_TEXT.get(item.get("status"), str(item.get("status"))))
            check_item = QTableWidgetItem("")
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            checked = str(item.get("path")) in saved
            check_item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            self.table.setItem(row, 0, type_item)
            self.table.setItem(row, 1, path_item)
            self.table.setItem(row, 2, status_item)
            self.table.setItem(row, 3, check_item)
        self.table.setUpdatesEnabled(True)
        self._loading_table = False
        self._apply_filter()
        self.verify_status.setText(f"共 {len(self._inventory)} 项，已恢复上次勾选 {len(saved)} 项")

    def _on_inventory_done(self, version_id):
        self.scan_btn.setEnabled(True)
        self.repair_selected_btn.setEnabled(bool(self._inventory))
        self.verify_progress.setVisible(False)
        abnormal = len([item for item in self._inventory if item.get("status") != "ok"])
        self.verify_status.setText("检查完成：" + f"{len(self._inventory)} 项，异常 {abnormal} 项")

    def _on_verify_error(self, message):
        self.scan_btn.setEnabled(True)
        self.verify_progress.setVisible(False)
        self.verify_status.setText("检查失败：" + str(message))

    def _apply_filter(self, *_args):
        mode = self.filter_combo.currentData()
        for row, item in enumerate(self._inventory):
            status = item.get("status")
            if mode == "all":
                visible = True
            elif mode == "abnormal":
                visible = status != "ok"
            else:
                visible = status == mode
            self.table.setRowHidden(row, not visible)

    def _checked_paths(self):
        paths = []
        for row in range(self.table.rowCount()):
            check_item = self.table.item(row, 3)
            path_item = self.table.item(row, 1)
            if check_item and path_item and check_item.checkState() == Qt.Checked:
                paths.append(path_item.text())
        return paths

    def select_abnormal(self):
        if not self._inventory:
            return
        self._loading_table = True
        for row, item in enumerate(self._inventory):
            check_item = self.table.item(row, 3)
            if check_item is None:
                continue
            check_item.setCheckState(Qt.Checked if item.get("status") != "ok" else Qt.Unchecked)
        self._loading_table = False
        self._persist_selection()

    def _persist_selection(self):
        version_id = self._verify_version or self.verify_combo.currentData()
        if version_id:
            self.settings.set_manual_selection(version_id, self._checked_paths())

    def _on_table_item_changed(self, item):
        if self._loading_table or item.column() != 3:
            return
        self._persist_selection()

    def repair_selected(self):
        version_id = self.verify_combo.currentData()
        paths = self._checked_paths()
        if not version_id:
            return
        if not paths:
            QMessageBox.information(self, "修复文件", "请先勾选需要修复的文件。")
            return
        self.repair_selected_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.verify_progress.setVisible(True)
        self.verify_progress.setRange(0, len(paths))
        self.verify_status.setText(f"正在修复 {len(paths)} 个文件…")
        task = self._track(worker.ManualRepairWorker(version_id, paths, self))
        task.progress.connect(self._on_repair_progress)
        task.finished_ok.connect(self._on_manual_repair_done)
        task.finished_error.connect(self._on_manual_repair_error)
        task.start()

    def _on_repair_progress(self, done, total):
        self.verify_progress.setRange(0, max(1, total))
        self.verify_progress.setValue(done)

    def _on_manual_repair_done(self, result):
        self.repair_selected_btn.setEnabled(True)
        self.scan_btn.setEnabled(True)
        self.verify_progress.setVisible(False)
        repaired = len(result.get("repaired") or [])
        failed = len(result.get("failed") or [])
        self.verify_status.setText(f"修复完成：成功 {repaired} 项，失败 {failed} 项")
        self._record_history(
            self.verify_combo.currentData() or "",
            "manual",
            "成功" if failed == 0 else f"部分失败({failed})",
        )
        QMessageBox.information(
            self,
            "修复结果",
            f"成功修复 {repaired} 项，失败 {failed} 项。\n失败详情可查看日志。",
        )
        self.scan_files()

    def _on_manual_repair_error(self, message):
        self.repair_selected_btn.setEnabled(True)
        self.scan_btn.setEnabled(True)
        self.verify_progress.setVisible(False)
        self.verify_status.setText("修复失败：" + str(message))

    def save_to_settings(self):
        self._persist_selection()
