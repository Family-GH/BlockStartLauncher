import html

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWidgets import QApplication

import config
from core import account_manager, system_open, worker
from core.icon_factory import create_nav_icon


class DeviceCodeDialog(QDialog):
    def __init__(self, user_code, verification_uri, parent=None):
        super().__init__(parent)
        self.setWindowTitle("微软登录")
        self.setMinimumWidth(500)
        self.user_code = user_code
        self.verification_uri = verification_uri
        self.cancelled = False
        layout = QVBoxLayout(self)
        instructions = QLabel(
            "浏览器会自动打开。把下面这串代码粘贴进去，然后按网页提示登录即可。\n"
            "如果浏览器没有自动打开，请点击下面的登录链接，或复制链接后手动打开。"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        self.code_label = QLabel(user_code)
        self.code_label.setAlignment(Qt.AlignCenter)
        self.code_label.setStyleSheet("font-size: 22pt; font-weight: 700; letter-spacing: 4px;")
        self.code_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.code_label)
        self.uri_label = QLabel()
        self.uri_label.setObjectName("Muted")
        self.uri_label.setWordWrap(True)
        self.uri_label.setAlignment(Qt.AlignCenter)
        self.uri_label.setTextFormat(Qt.RichText)
        self.uri_label.setOpenExternalLinks(False)
        self.uri_label.linkActivated.connect(self._open_link)
        if verification_uri:
            escaped = html.escape(verification_uri)
            self.uri_label.setText(
                '<a style="color:#7DD3FC;" href="%s">%s</a>' % (escaped, escaped)
            )
            self.uri_label.setToolTip("点击在浏览器中打开")
        else:
            self.uri_label.setText("未能获取登录链接，请重新登录。")
        layout.addWidget(self.uri_label)
        row = QHBoxLayout()
        copy_btn = QPushButton("复制代码")
        copy_btn.clicked.connect(self._copy_code)
        row.addWidget(copy_btn)
        copy_link_btn = QPushButton("复制登录链接")
        copy_link_btn.clicked.connect(self._copy_link)
        row.addWidget(copy_link_btn)
        browser_btn = QPushButton("打开浏览器")
        browser_btn.setObjectName("PrimaryButton")
        browser_btn.clicked.connect(lambda: self._open_browser())
        row.addWidget(browser_btn)
        cancel_btn = QPushButton("取消登录")
        cancel_btn.clicked.connect(self._cancel)
        row.addWidget(cancel_btn)
        layout.addLayout(row)
        self.status_label = QLabel("代码已自动复制。等待浏览器中完成登录…")
        self.status_label.setObjectName("Muted")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _copy_code(self):
        try:
            QApplication.clipboard().setText(self.user_code)
            self.status_label.setText("设备代码已复制，可粘贴到微软登录页面")
        except Exception as exc:
            self.status_label.setText("复制失败：" + str(exc))

    def _copy_link(self):
        if not self.verification_uri:
            self.status_label.setText("没有可复制的登录链接")
            return
        try:
            QApplication.clipboard().setText(self.verification_uri)
            self.status_label.setText("登录链接已复制，请粘贴到浏览器地址栏")
        except Exception as exc:
            self.status_label.setText("复制失败：" + str(exc))

    def _open_link(self, url):
        self._open_browser(url)

    def _open_browser(self, url=None, show_error=True):
        target = str(url or self.verification_uri or "").strip()
        if not target:
            self.status_label.setText("没有登录链接，请取消后重新登录")
            return False
        ok, error = system_open.open_url(target)
        if ok:
            self.status_label.setText("已打开浏览器，请完成登录")
            return True
        self.status_label.setText(
            "浏览器没有自动打开。请点击上面的链接，或复制登录链接手动打开。"
        )
        if show_error:
            QMessageBox.warning(
                self,
                "无法自动打开浏览器",
                "系统没有成功打开默认浏览器。\n\n"
                "你仍然可以：\n"
                "1. 点击窗口里的蓝色登录链接；\n"
                "2. 或点“复制登录链接”，粘贴到浏览器地址栏。\n\n"
                "详细信息：" + error,
            )
        return False

    def _cancel(self):
        self.cancelled = True
        self.reject()

    def reject(self):
        self.cancelled = True
        super().reject()

    def closeEvent(self, event):
        # Closing with the window X must also cancel the polling worker,
        # otherwise login appears to wait forever with no visible dialog.
        self.cancelled = True
        super().closeEvent(event)



class AccountPage(QWidget):
    account_changed = Signal(str)

    def __init__(self, settings, host, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.host = host
        self._loading = True
        self._workers = []
        self._login_dialog = None
        self._login_cancelled = False
        self._skin_dialog = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        title = QLabel("账户管理")
        title.setStyleSheet("font-size: 17pt; font-weight: 700;")
        layout.addWidget(title)
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selection)
        layout.addWidget(self.list_widget, 1)
        row = QHBoxLayout()
        self.offline_btn = QPushButton("离线账户（免登录）")
        self.offline_btn.setObjectName("PrimaryButton")
        self.offline_btn.clicked.connect(self.add_offline)
        row.addWidget(self.offline_btn)
        self.ms_btn = QPushButton("微软正版登录（推荐）")
        self.ms_btn.clicked.connect(self.login_microsoft)
        row.addWidget(self.ms_btn)
        self.refresh_btn = QPushButton("刷新令牌")
        self.refresh_btn.clicked.connect(self.refresh_token)
        row.addWidget(self.refresh_btn)
        self.skin_btn = QPushButton("皮肤与披风")
        self.skin_btn.clicked.connect(self.open_skin_dialog)
        row.addWidget(self.skin_btn)
        self.delete_btn = QPushButton("删除账户")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self.delete_account)
        row.addWidget(self.delete_btn)
        layout.addLayout(row)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        layout.addWidget(self.status_label)
        self._update_buttons()

    def refresh(self, select_id=None):
        self._loading = True
        self.list_widget.clear()
        accounts = account_manager.list_accounts()
        target = select_id or self.settings.get("last_account_uuid") or ""
        selected = None
        for account in accounts:
            label = "微软账户" if account.get("type") == "msa" else "离线账户"
            item = QListWidgetItem(f"{account.get('username') or 'Player'}\n{label}")
            item.setIcon(create_nav_icon("account"))
            item.setData(Qt.UserRole, account.get("id"))
            self.list_widget.addItem(item)
            if account.get("id") == target:
                selected = item
        if not accounts:
            placeholder = QListWidgetItem("暂无账户，点击“添加离线账户”或“微软登录”")
            placeholder.setFlags(Qt.NoItemFlags)
            self.list_widget.addItem(placeholder)
        if selected is None and accounts:
            offline = next((account for account in accounts if account.get("type") != "msa"), accounts[0])
            for index in range(self.list_widget.count()):
                item = self.list_widget.item(index)
                if item.data(Qt.UserRole) == offline.get("id"):
                    selected = item
                    break
        if selected is not None:
            self.list_widget.setCurrentItem(selected)
        self._loading = False
        current = self.current_account_id()
        if current:
            self.settings.set("last_account_uuid", current)
        self._update_buttons()

    def current_account_id(self):
        item = self.list_widget.currentItem()
        if not item:
            return ""
        return str(item.data(Qt.UserRole) or "")

    def _on_selection(self, *_args):
        if self._loading:
            return
        account_id = self.current_account_id()
        if not account_id:
            return
        self.settings.set("last_account_uuid", account_id)
        self.settings.save()
        self.account_changed.emit(account_id)
        self._update_buttons()

    def _update_buttons(self):
        has_account = bool(self.current_account_id())
        account = self._current_account()
        is_msa = bool(account and account.get("type") == "msa")
        self.refresh_btn.setEnabled(has_account)
        self.delete_btn.setEnabled(has_account)
        self.skin_btn.setEnabled(is_msa)
        self.skin_btn.setToolTip(
            "查看、上传皮肤和更换披风" if is_msa else "离线账户没有官方皮肤，请先登录微软账户"
        )

    def _current_account(self):
        account_id = self.current_account_id()
        return next(
            (item for item in account_manager.list_accounts() if item.get("id") == account_id),
            None,
        )

    def open_skin_dialog(self):
        account = self._current_account()
        if not account:
            QMessageBox.information(self, "皮肤与披风", "请先选择一个账户。")
            return
        if account.get("type") != "msa":
            QMessageBox.information(
                self,
                "皮肤与披风",
                "离线账户没有 Mojang 官方皮肤和披风。\n请使用“微软正版登录”后再试。",
            )
            return
        from ui.skin_dialog import SkinCapeDialog

        dialog = SkinCapeDialog(account, self._client_id(), self.host, self)
        self._skin_dialog = dialog
        dialog.exec()
        self._skin_dialog = None


    def _client_id(self):
        return str(self.settings.get("ms_client_id") or config.MS_CLIENT_ID or "").strip()

    def add_offline(self):
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "添加离线账户", "玩家名称：", text="Player")
        if not ok:
            return
        if not name.strip():
            QMessageBox.warning(self, "添加失败", "玩家名称不能为空。")
            return
        try:
            account = account_manager.add_offline(name.strip())
        except Exception as exc:
            QMessageBox.critical(self, "添加失败", "无法安全保存账户：" + str(exc))
            return
        self.refresh(account.get("id"))
        self.account_changed.emit(account.get("id"))
        self.settings.set("last_account_uuid", account.get("id") or "")
        self.settings.save()
        self.status_label.setText("已添加离线账户：" + account.get("username", ""))

    def login_microsoft(self):
        client_id = self._client_id()
        if not client_id:
            QMessageBox.information(self, "微软登录", "请先在设置页填写 Azure client_id。")
            return
        self.ms_btn.setEnabled(False)
        self._login_cancelled = False
        self.status_label.setText("正在请求设备代码…")
        task = worker.MSLoginWorker(client_id, self)
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        task.device_code_ready.connect(self._show_device_code)
        task.status_changed.connect(self.status_label.setText)
        task.finished_ok.connect(self._on_login_ok)
        task.finished_error.connect(self._on_login_error)
        task.start()

    def _show_device_code(self, user_code, verification_uri):
        self.status_label.setText("等待微软登录…")
        try:
            QApplication.clipboard().setText(user_code)
        except Exception:
            pass
        dialog = DeviceCodeDialog(user_code, verification_uri, self)
        self._login_dialog = dialog
        dialog.finished.connect(self._on_dialog_closed)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        if verification_uri:
            # Give the dialog a chance to paint before ShellExecute steals
            # focus.  Failure is non-fatal: the dialog also offers a clickable
            # link and a copy-link button.
            QTimer.singleShot(
                300,
                lambda d=dialog: d._open_browser(show_error=False)
                if self._login_dialog is d
                else None,
            )


    def _on_dialog_closed(self, _result):
        dialog = self._login_dialog
        if dialog and dialog.cancelled:
            self._login_cancelled = True
            for task in self._workers:
                if isinstance(task, worker.MSLoginWorker) and task.isRunning():
                    task.cancel()
            self.status_label.setText("已取消微软登录")
            self.ms_btn.setEnabled(True)
        self._login_dialog = None

    def _close_login_dialog(self):
        dialog = self._login_dialog
        if dialog is not None:
            self._login_dialog = None
            dialog.blockSignals(True)
            dialog.accept()
            dialog.blockSignals(False)

    def _on_login_ok(self, account):
        self.ms_btn.setEnabled(True)
        self._login_cancelled = False
        self.status_label.setText("微软登录成功：" + str(account.get("username") or ""))
        self._close_login_dialog()
        self.refresh(account.get("id"))
        self.account_changed.emit(account.get("id"))

    def _on_login_error(self, message):
        self.ms_btn.setEnabled(True)
        self._close_login_dialog()
        if self._login_cancelled:
            self._login_cancelled = False
            self.status_label.setText("已取消微软登录")
            return
        self.status_label.setText("微软登录失败：" + str(message))
        QMessageBox.warning(self, "微软登录失败", str(message))

    def refresh_token(self):
        account_id = self.current_account_id()
        if not account_id:
            return
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("正在刷新登录令牌…")
        task = worker.AccountRefreshWorker(account_id, self._client_id(), self)
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        task.finished_ok.connect(self._on_refresh_ok)
        task.finished_error.connect(self._on_refresh_error)
        task.start()

    def _on_refresh_ok(self, account):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText("登录令牌已刷新")
        if isinstance(account, dict):
            self.refresh(account.get("id"))

    def _on_refresh_error(self, message):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText("刷新失败：" + str(message))
        QMessageBox.warning(self, "刷新令牌失败", str(message))

    def delete_account(self):
        account_id = self.current_account_id()
        if not account_id:
            return
        account = next(
            (item for item in account_manager.list_accounts() if item.get("id") == account_id), None
        )
        name = account.get("username") if account else account_id
        answer = QMessageBox.question(
            self,
            "删除账户",
            f"确定删除账户“{name}”吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        account_manager.remove(account_id)
        self.settings.set("last_account_uuid", "")
        self.refresh()
        self.account_changed.emit(self.current_account_id())
        self.status_label.setText("已删除账户：" + str(name))

    def save_to_settings(self):
        account_id = self.current_account_id()
        if account_id:
            self.settings.set("last_account_uuid", account_id)
