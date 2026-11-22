from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import config
from core import worker

# UV rectangles in the 64x64 skin texture.  Kept here (rather than loading a
# model) so the preview works offline and adds no runtime dependency.
FRONT = {
    "head": (8, 8, 8, 8),
    "hat": (40, 8, 8, 8),
    "body": (20, 20, 8, 12),
    "jacket": (20, 36, 8, 12),
    "right_arm": (44, 20, 4, 12),
    "right_sleeve": (44, 36, 4, 12),
    "left_arm": (36, 52, 4, 12),
    "left_sleeve": (52, 52, 4, 12),
    "right_leg": (4, 20, 4, 12),
    "right_pants": (4, 36, 4, 12),
    "left_leg": (20, 52, 4, 12),
    "left_pants": (4, 52, 4, 12),
}
BACK = {
    "head": (24, 8, 8, 8),
    "hat": (56, 8, 8, 8),
    "body": (32, 20, 8, 12),
    "jacket": (32, 36, 8, 12),
    "right_arm": (52, 20, 4, 12),
    "right_sleeve": (52, 36, 4, 12),
    "left_arm": (44, 52, 4, 12),
    "left_sleeve": (60, 52, 4, 12),
    "right_leg": (12, 20, 4, 12),
    "right_pants": (12, 36, 4, 12),
    "left_leg": (28, 52, 4, 12),
    "left_pants": (12, 52, 4, 12),
}

# Alex/slim skins use 3-pixel arms.  The fourth arm column in a 64x64 texture
# is padding and must not be stretched over a 4-pixel preview arm.
SLIM_FRONT = dict(FRONT)
SLIM_FRONT.update({
    "right_arm": (44, 20, 3, 12),
    "right_sleeve": (44, 36, 3, 12),
    "left_arm": (36, 52, 3, 12),
    "left_sleeve": (52, 52, 3, 12),
})
SLIM_BACK = dict(BACK)
SLIM_BACK.update({
    "right_arm": (52, 20, 3, 12),
    "right_sleeve": (52, 36, 3, 12),
    "left_arm": (44, 52, 3, 12),
    "left_sleeve": (60, 52, 3, 12),
})


def _alpha(image, x, y):
    if image.isNull() or x < 0 or y < 0 or x >= image.width() or y >= image.height():
        return 0
    return image.pixelColor(x, y).alpha()


def detect_variant(image):
    """Best-effort Steve/Alex detection for a 64x64 skin.

    Minecraft does not store the model in the PNG.  Slim skins reserve the
    fourth column of both arm faces as transparent padding; use that as a
    hint and let the user override it in the dialog.
    """
    if image.isNull() or image.width() != 64 or image.height() < 64:
        return "classic"
    right_pad = all(_alpha(image, 47, 20 + i) == 0 for i in range(12))
    left_pad = all(_alpha(image, 39, 52 + i) == 0 for i in range(12))
    has_arm = any(_alpha(image, 44 + i, 20 + j) > 0 for i in range(3) for j in range(12))
    if right_pad and left_pad and has_arm:
        return "slim"
    return "classic"


class SkinPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 390)
        self.skin = QImage()
        self.cape = QImage()
        self.back = False
        self.variant = "classic"
        self.show_overlay = True
        self.player_name = ""

    def set_skin(self, data, variant=None):
        image = QImage.fromData(data) if data else QImage()
        self.skin = image.convertToFormat(QImage.Format_ARGB32) if not image.isNull() else QImage()
        if variant in ("classic", "slim"):
            self.variant = variant
        elif not self.skin.isNull():
            self.variant = detect_variant(self.skin)
        self.update()

    def set_variant(self, variant):
        self.variant = "slim" if variant == "slim" else "classic"
        self.update()

    def set_overlay(self, visible):
        self.show_overlay = bool(visible)
        self.update()

    def set_cape(self, data):
        image = QImage.fromData(data) if data else QImage()
        self.cape = image.convertToFormat(QImage.Format_ARGB32) if not image.isNull() else QImage()
        self.update()

    def set_back(self, back):
        self.back = bool(back)
        self.update()

    def _source(self, key):
        if self.skin.isNull():
            return None
        table = (SLIM_BACK if self.back else SLIM_FRONT) if self.variant == "slim" else (BACK if self.back else FRONT)
        if key not in table:
            return None
        x, y, w, h = table[key]
        if x + w <= self.skin.width() and y + h <= self.skin.height():
            return self.skin.copy(x, y, w, h)
        # 64x32 legacy skins only contain the right arm/leg; Minecraft mirrors
        # them for the left side.  Mirror instead of showing a solid limb.
        if self.skin.height() <= 32 and key.startswith("left_"):
            mirror_key = "right_" + key[5:]
            if mirror_key in table:
                mx, my, mw, mh = table[mirror_key]
                if mx + mw <= self.skin.width() and my + mh <= self.skin.height():
                    return self.skin.copy(mx, my, mw, mh).mirrored(True, False)
        return None

    def _part(self, painter, target, key, fallback):
        source = self._source(key)
        if source is None or source.isNull():
            painter.fillRect(QRectF(*target), QColor(fallback))
            return
        painter.drawImage(QRectF(*target), source)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        background = QLinearGradient(0, 0, 0, rect.height())
        background.setColorAt(0, QColor("#13233f"))
        background.setColorAt(1, QColor("#0b1220"))
        painter.setBrush(background)
        painter.setPen(QPen(QColor("#243b5a"), 1))
        painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), 18, 18)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawEllipse(QRectF(rect.width() / 2 - 72, rect.height() - 72, 144, 28))

        slim = self.variant == "slim"
        arm_w = 3 if slim else 4
        model_w = 8 + arm_w * 2
        unit = min(rect.width() / (model_w + 6.0), (rect.height() - 80) / 34.0)
        width = model_w * unit
        x = (rect.width() - width) / 2
        y = 26
        body_x = x + arm_w * unit
        head = (body_x, y, 8 * unit, 8 * unit)
        body = (body_x, y + 8 * unit, 8 * unit, 12 * unit)
        right_arm = (x, y + 8 * unit, arm_w * unit, 12 * unit)
        left_arm = (body_x + 8 * unit, y + 8 * unit, arm_w * unit, 12 * unit)
        right_leg = (body_x, y + 20 * unit, 4 * unit, 12 * unit)
        left_leg = (body_x + 4 * unit, y + 20 * unit, 4 * unit, 12 * unit)
        cape_rect = (body_x - 1 * unit, y + 8 * unit, 10 * unit, 16 * unit)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)

        if not self.back and not self.cape.isNull():
            self._draw_cape(painter, cape_rect)

        self._part(painter, right_leg, "right_leg", "#43516a")
        self._part(painter, left_leg, "left_leg", "#43516a")
        self._part(painter, right_arm, "right_arm", "#43516a")
        self._part(painter, left_arm, "left_arm", "#43516a")
        self._part(painter, body, "body", "#52627c")
        self._part(painter, head, "head", "#7b8aa3")
        if self.show_overlay:
            self._part(painter, head, "hat", "#00000000")
            self._part(painter, right_arm, "right_sleeve", "#00000000")
            self._part(painter, left_arm, "left_sleeve", "#00000000")
            self._part(painter, body, "jacket", "#00000000")
            self._part(painter, right_leg, "right_pants", "#00000000")
            self._part(painter, left_leg, "left_pants", "#00000000")

        if self.back and not self.cape.isNull():
            self._draw_cape(painter, cape_rect)

        painter.setPen(QColor("#8ea7c4"))
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, rect.height() - 38, rect.width(), 24),
            Qt.AlignCenter,
            (self.player_name or "皮肤预览") + ("（背面）" if self.back else ""),
        )
        painter.end()

    def _draw_cape(self, painter, target):
        if self.cape.isNull():
            return
        source = QRectF(1, 1, 10, 16)
        if self.cape.width() < 12 or self.cape.height() < 17:
            source = QRectF(0, 0, self.cape.width(), self.cape.height())
        painter.drawImage(QRectF(*target), self.cape, source)


class SkinCapeDialog(QDialog):
    def __init__(self, account, client_id="", host=None, parent=None):
        super().__init__(parent)
        self.account = dict(account or {})
        self.client_id = client_id
        self.host = host
        self._workers = []
        self._busy = False
        self._selected_file = ""
        self._active_cape = ""
        self._cape_data = {}
        self.setWindowTitle("皮肤与披风")
        self.setMinimumSize(820, 580)
        self._build_ui()
        self._set_busy(False)
        if self.account.get("type") != "msa":
            self._show_offline()
        else:
            self.load_profile()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(18)
        left = QVBoxLayout()
        self.preview = SkinPreview(self)
        left.addWidget(self.preview, 1)
        self.view_btn = QPushButton("查看背面")
        self.view_btn.clicked.connect(self._toggle_view)
        left.addWidget(self.view_btn)
        self.overlay_check = QCheckBox("显示第二层（帽子/外套/裤腿）")
        self.overlay_check.setChecked(True)
        self.overlay_check.toggled.connect(self.preview.set_overlay)
        left.addWidget(self.overlay_check)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        title = QLabel("皮肤与披风")
        title.setStyleSheet("font-size: 17pt; font-weight: 700;")
        right.addWidget(title)
        self.account_label = QLabel("")
        self.account_label.setObjectName("Muted")
        right.addWidget(self.account_label)

        skin_group = QGroupBox("皮肤")
        skin_layout = QVBoxLayout(skin_group)
        self.skin_status = QLabel("正在获取…")
        self.skin_status.setWordWrap(True)
        skin_layout.addWidget(self.skin_status)
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("模型"))
        self.variant_combo = QComboBox()
        self.variant_combo.addItem("自动识别（推荐）", "auto")
        self.variant_combo.addItem("经典（Steve，4 像素手臂）", "classic")
        self.variant_combo.addItem("纤细（Alex，3 像素手臂）", "slim")
        self.variant_combo.currentIndexChanged.connect(self._variant_changed)
        model_row.addWidget(self.variant_combo, 1)
        skin_layout.addLayout(model_row)
        choose_row = QHBoxLayout()
        self.choose_btn = QPushButton("选择本地皮肤…")
        self.choose_btn.clicked.connect(self.choose_file)
        choose_row.addWidget(self.choose_btn)
        self.upload_btn = QPushButton("上传皮肤")
        self.upload_btn.setObjectName("PrimaryButton")
        self.upload_btn.clicked.connect(self.upload_skin)
        choose_row.addWidget(self.upload_btn)
        self.reset_btn = QPushButton("恢复默认皮肤")
        self.reset_btn.clicked.connect(self.reset_skin)
        choose_row.addWidget(self.reset_btn)
        skin_layout.addLayout(choose_row)
        right.addWidget(skin_group)

        cape_group = QGroupBox("披风")
        cape_layout = QVBoxLayout(cape_group)
        self.cape_status = QLabel("正在获取披风…")
        self.cape_status.setWordWrap(True)
        cape_layout.addWidget(self.cape_status)
        self.cape_combo = QComboBox()
        self.cape_combo.currentIndexChanged.connect(self._preview_selected_cape)
        cape_layout.addWidget(self.cape_combo)
        cape_row = QHBoxLayout()
        self.apply_cape_btn = QPushButton("使用所选披风")
        self.apply_cape_btn.setObjectName("PrimaryButton")
        self.apply_cape_btn.clicked.connect(self.apply_cape)
        cape_row.addWidget(self.apply_cape_btn)
        self.hide_cape_btn = QPushButton("隐藏披风")
        self.hide_cape_btn.clicked.connect(self.hide_cape)
        cape_row.addWidget(self.hide_cape_btn)
        cape_layout.addLayout(cape_row)
        right.addWidget(cape_group)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        right.addWidget(self.progress)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        right.addWidget(self.status_label)
        right.addStretch(1)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        right.addWidget(close_btn, 0, Qt.AlignRight)
        layout.addLayout(right, 1)

    def _effective_variant(self):
        selected = str(self.variant_combo.currentData() or "auto")
        if selected == "slim":
            return "slim"
        if selected == "classic":
            return "classic"
        detected = detect_variant(self.preview.skin)
        return detected if detected in ("classic", "slim") else "classic"

    def _variant_changed(self, _index=0):
        self.preview.set_variant(self._effective_variant())
        if not self.preview.skin.isNull():
            self.skin_status.setText(
                "预览模型：%s。若皮肤手臂在游戏里变形，请手动切换经典/纤细。"
                % ("纤细 Alex" if self._effective_variant() == "slim" else "经典 Steve")
            )

    def _show_offline(self):
        self.account_label.setText("离线账户")
        self.skin_status.setText("离线账户没有 Mojang 官方皮肤。登录微软账户后即可查看、上传和更换披风。")
        self.cape_status.setText("登录微软账户后可管理披风。")
        self.choose_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.apply_cape_btn.setEnabled(False)
        self.hide_cape_btn.setEnabled(False)
        self.variant_combo.setEnabled(False)
        self.preview.set_skin(b"")
        self.preview.player_name = str(self.account.get("username") or "Steve")

    def _set_busy(self, busy):
        self._busy = bool(busy)
        enabled = not busy and self.account.get("type") == "msa"
        self.choose_btn.setEnabled(enabled)
        self.upload_btn.setEnabled(enabled and bool(self._selected_file))
        self.reset_btn.setEnabled(enabled)
        self.cape_combo.setEnabled(enabled)
        self.apply_cape_btn.setEnabled(enabled and self.cape_combo.count() > 0)
        self.hide_cape_btn.setEnabled(enabled)
        self.variant_combo.setEnabled(enabled)
        self.progress.setVisible(busy)

    def _run(self, task, on_ok, on_error=None):
        self._workers.append(task)
        if self.host:
            self.host.attach_worker(task)
        task.finished_ok.connect(on_ok)
        task.finished_error.connect(on_error or self._on_error)
        task.start()

    def load_profile(self):
        if self._busy:
            return
        self._set_busy(True)
        self.status_label.setText("正在从 Minecraft 服务获取皮肤与披风…")
        task = worker.SkinProfileWorker(self.account.get("id") or "", self.client_id, self)
        self._run(task, self._on_profile)

    def _preview_selected_cape(self, index=0):
        cape_id = str(self.cape_combo.itemData(index) or "") if index >= 0 else ""
        self.preview.set_cape(self._cape_data.get(cape_id, b""))

    def _on_profile(self, data):
        self._set_busy(False)
        data = data if isinstance(data, dict) else {}
        profile = data.get("profile") or {}
        name = profile.get("name") or self.account.get("username") or "玩家"
        self.account_label.setText("微软账户：" + str(name))
        self.preview.player_name = str(name)
        self.preview.set_skin(data.get("skin") or b"")
        skins = profile.get("skins") or []
        if skins:
            variant = str(skins[0].get("variant") or "").upper()
            index = 2 if variant == "SLIM" else 1
            self.variant_combo.setCurrentIndex(index)
            self.preview.set_variant("slim" if variant == "SLIM" else "classic")
            self.skin_status.setText("已加载当前皮肤，可上传 64×64 或 64×32 的 PNG；模型已按账户设置。")
        else:
            self.variant_combo.setCurrentIndex(0)
            self.preview.set_variant(detect_variant(self.preview.skin))
            self.skin_status.setText("当前使用默认皮肤。选择 PNG 后会自动识别 Steve/Alex，也可手动切换。")
        self.cape_combo.clear()
        self._cape_data = {}
        self.cape_combo.addItem("不使用披风", "")
        capes = data.get("capes") or []
        self._active_cape = str(data.get("active_cape") or "")
        active_index = 0
        active_cape_data = b""
        for cape in capes:
            if not isinstance(cape, dict):
                continue
            cape_id = str(cape.get("id") or "")
            self._cape_data[cape_id] = cape.get("data") or b""
            self.cape_combo.addItem(str(cape.get("alias") or "披风"), cape_id)
            if cape_id == self._active_cape:
                active_index = self.cape_combo.count() - 1
                active_cape_data = cape.get("data") or b""
        self.cape_combo.setCurrentIndex(active_index)
        if active_cape_data:
            self.preview.set_cape(active_cape_data)
        else:
            self.preview.set_cape(b"")
        if capes:
            self.cape_status.setText(f"拥有 {len(capes)} 件披风，选择后点“使用所选披风”。")
        else:
            self.cape_status.setText("该账户没有可用披风。")
        self._set_busy(False)
        self.status_label.setText("皮肤与披风已同步。")

    def _on_error(self, message):
        self._set_busy(False)
        self.status_label.setText("操作失败：" + str(message))
        QMessageBox.warning(self, "皮肤与披风", str(message))

    def _toggle_view(self):
        self.preview.set_back(not self.preview.back)
        self.view_btn.setText("查看正面" if self.preview.back else "查看背面")

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择皮肤 PNG", "", "PNG 图片 (*.png)")
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "皮肤文件", "无法读取这个 PNG 文件。")
            return
        if (image.width(), image.height()) not in ((64, 64), (64, 32)):
            QMessageBox.warning(self, "皮肤文件", "皮肤尺寸必须是 64×64 或 64×32 像素。")
            return
        self._selected_file = path
        try:
            with open(path, "rb") as handle:
                skin_data = handle.read()
        except OSError as exc:
            QMessageBox.warning(self, "皮肤文件", "无法读取这个文件：\n" + str(exc))
            return
        self.preview.set_skin(skin_data)
        if self.variant_combo.currentData() == "auto":
            self.preview.set_variant(detect_variant(self.preview.skin))
        else:
            self.preview.set_variant(self.variant_combo.currentData())
        variant = self._effective_variant()
        layer_note = "含第二层" if image.height() >= 64 else "旧版 64×32"
        self.skin_status.setText(
            "已选择：%s（%d×%d，%s 模型，%s）"
            % (path.rsplit("\\", 1)[-1], image.width(), image.height(),
               "Alex 纤细" if variant == "slim" else "Steve 经典", layer_note)
        )
        self._set_busy(False)

    def upload_skin(self):
        if not self._selected_file:
            QMessageBox.information(self, "上传皮肤", "请先选择一个 PNG 皮肤文件。")
            return
        self._set_busy(True)
        self.status_label.setText("正在上传皮肤…")
        task = worker.SkinActionWorker(
            "upload",
            self.account.get("id") or "",
            self.client_id,
            file_path=self._selected_file,
            variant=self._effective_variant(),
            parent=self,
        )
        self._run(task, lambda _data: self._after_action("皮肤已上传。"))

    def reset_skin(self):
        if QMessageBox.question(
            self, "恢复默认皮肤", "确定恢复为默认皮肤吗？", QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        self._set_busy(True)
        task = worker.SkinActionWorker(
            "reset", self.account.get("id") or "", self.client_id, parent=self
        )
        self._run(task, lambda _data: self._after_action("已恢复默认皮肤。"))

    def apply_cape(self):
        cape_id = str(self.cape_combo.currentData() or "")
        if not cape_id:
            self.hide_cape()
            return
        self._set_busy(True)
        task = worker.SkinActionWorker(
            "cape",
            self.account.get("id") or "",
            self.client_id,
            cape_id=cape_id,
            parent=self,
        )
        self._run(task, lambda _data: self._after_action("披风已更换。"))

    def hide_cape(self):
        self._set_busy(True)
        task = worker.SkinActionWorker(
            "cape", self.account.get("id") or "", self.client_id, parent=self
        )
        self._run(task, lambda _data: self._after_action("披风已隐藏。"))

    def _after_action(self, message):
        self._selected_file = ""
        self._set_busy(False)
        self.status_label.setText(message + " 正在刷新…")
        self.load_profile()

    def closeEvent(self, event):
        if self._busy:
            self.status_label.setText("正在完成网络操作，请稍候再关闭…")
            event.ignore()
            return
        for task in self._workers:
            if task.isRunning():
                task.cancel()
                task.wait(1500)
        super().closeEvent(event)
