from pathlib import Path

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QWidget

from ui.ConfirmDialog import ConfirmDialog
from ui.resource_pack_selector.css import DELETE_BUTTON_STYLE, LIST_ITEM_STYLE
from util.log import _log
from util.i18n import tr


class ResourcePackListItem(QWidget):
    """自定义资源包列表项，鼠标悬停时显示删除图标"""

    def __init__(self, display_name: str, file_name: str, parent_selector=None, parent=None):
        super().__init__(parent)
        self.display_name = display_name
        self.file_name = file_name
        self.parent_selector = parent_selector
        self.setMouseTracking(True)

        # 设置widget背景透明，禁用默认hover样式
        self.setStyleSheet(LIST_ITEM_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(10)

        label = QLabel(f"{display_name}    ({file_name})")
        label.setStyleSheet("color: #f0f0f0; font-size: 13px;")
        label.setCursor(Qt.ArrowCursor)
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(label, 1)

        self.delete_button = QPushButton("✕")
        self.delete_button.setObjectName("deleteButton")
        self.delete_button.setFixedSize(10, 10)
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.setToolTip(tr("resource_selector.delete.tooltip"))
        self.delete_button.setVisible(False)
        self.delete_button.setStyleSheet(DELETE_BUTTON_STYLE)
        self.delete_button.clicked.connect(self._on_delete)
        layout.addWidget(self.delete_button, 0, Qt.AlignRight | Qt.AlignVCenter)

    def _delete_hotspot_rect(self) -> QRect:
        # 仅在按钮附近热点区域显示删除按钮，避免整行悬停触发
        margins = self.layout().contentsMargins()
        btn_w = self.delete_button.width()
        btn_h = self.delete_button.height()
        x = self.width() - margins.right() - btn_w
        y = (self.height() - btn_h) // 2
        return QRect(max(0, x - 4), max(0, y - 4), btn_w + 8, btn_h + 8)

    def _update_delete_button_visibility(self, pos):
        self.delete_button.setVisible(self._delete_hotspot_rect().contains(pos))

    def enterEvent(self, event):
        self._update_delete_button_visibility(self.mapFromGlobal(QCursor.pos()))
        super().enterEvent(event)

    def mouseMoveEvent(self, event):
        self._update_delete_button_visibility(event.position().toPoint())
        super().mouseMoveEvent(event)

    def resizeEvent(self, event):
        self._update_delete_button_visibility(self.mapFromGlobal(QCursor.pos()))
        super().resizeEvent(event)

    def leaveEvent(self, event):
        self.delete_button.setVisible(False)
        super().leaveEvent(event)

    def _on_delete(self):
        if self.file_name == "image.json":
            dialog = ConfirmDialog(
                tr("resource_selector.dialog.cannot_delete_title"),
                tr("resource_selector.dialog.cannot_delete_msg"),
            )
            dialog.confirm_button.setVisible(False)
            dialog.exec()
            return

        dialog = ConfirmDialog(
            tr("resource_selector.dialog.confirm_delete_title"),
            tr("resource_selector.dialog.confirm_delete_msg", display=self.display_name, file=self.file_name),
        )
        if dialog.exec() != QDialog.Accepted:
            return

        try:
            pack_path = Path("resources") / self.file_name
            if pack_path.exists():
                pack_path.unlink()
                _log.INFO(f"已删除资源包: {self.file_name}")
                if self.parent_selector:
                    self.parent_selector._on_pack_deleted(self.file_name)
            else:
                error_dialog = ConfirmDialog(
                    tr("resource_selector.dialog.delete_failed_title"),
                    tr("resource_selector.dialog.file_not_exist", file=self.file_name),
                )
                error_dialog.confirm_button.setVisible(False)
                error_dialog.exec()
        except Exception as e:
            error_dialog = ConfirmDialog(
                tr("resource_selector.dialog.delete_failed_title"),
                tr("resource_selector.dialog.delete_failed_msg", error=str(e)),
            )
            error_dialog.confirm_button.setVisible(False)
            error_dialog.exec()
            _log.ERROR(f"删除资源包失败 {self.file_name}: {e}")
