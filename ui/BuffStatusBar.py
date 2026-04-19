"""
Buff 状态显示栏

在宠物右侧竖向显示最多三个 buff 状态图标（32x32），固定三个位置。
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from util.buff_icon_manager import BuffIconManager
from util.i18n import tr
from util.log import _log


# ─────────────────────────────────────────────────────────────────────────────
# Hover 悬浮弹窗（与养成面板样式一致）
# ─────────────────────────────────────────────────────────────────────────────

class BuffHoverPopup(QFrame):
    """Buff 悬浮弹窗，样式与养成面板一致。"""

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("buffHoverPopupRoot")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.panel = QFrame(self)
        self.panel.setObjectName("buffHoverPopup")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        panel_layout.setSpacing(4)

        self.name_label = QLabel()
        self.name_label.setObjectName("titleLabel")
        self.name_label.setWordWrap(True)
        panel_layout.addWidget(self.name_label)

        self.desc_label = QLabel()
        self.desc_label.setObjectName("detailLabel")
        self.desc_label.setWordWrap(True)
        self.desc_label.setMaximumWidth(200)
        panel_layout.addWidget(self.desc_label)

        outer.addWidget(self.panel)

        self.setStyleSheet(
            "QFrame#buffHoverPopupRoot { background: transparent; border: none; }"
            "QFrame#buffHoverPopup {"
            "  background-color: #111820;"
            "  border: 1px solid #2e4d6b;"
            "  border-radius: 10px;"
            "}"
            "QLabel#titleLabel {"
            "  color: #8ec8ff;"
            "  font-size: 11px;"
            "  font-weight: 700;"
            "  letter-spacing: 0.5px;"
            "  background: transparent;"
            "  border: none;"
            "}"
            "QLabel#detailLabel {"
            "  color: #b9d7ee;"
            "  font-size: 11px;"
            "  background: transparent;"
            "  border: none;"
            "}"
        )

    def show_for(self, *, name: str, desc: str, global_pos: QPoint) -> None:
        self.name_label.setText(name)
        self.desc_label.setText(desc)
        self.desc_label.setVisible(bool(desc))
        self.adjustSize()
        self.move(global_pos + QPoint(14, 18))
        self.show()


# 模块级单例
_popup_instance: Optional[BuffHoverPopup] = None


def _get_popup() -> BuffHoverPopup:
    global _popup_instance
    if _popup_instance is None:
        _popup_instance = BuffHoverPopup()
    return _popup_instance


# ─────────────────────────────────────────────────────────────────────────────
# 单个图标槽
# ─────────────────────────────────────────────────────────────────────────────

class BuffStatusIcon(QLabel):
    """单个 Buff 状态图标槽，固定 32×32，竖向排布。"""

    ICON_SIZE = 32

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.ICON_SIZE, self.ICON_SIZE)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMouseTracking(True)
        self._current_buff: Optional[Dict[str, Any]] = None
        self.setVisible(False)

    # ── 数据设置 ────────────────────────────────────────

    def set_buff(self, buff_data: Optional[Dict[str, Any]]) -> None:
        self._current_buff = buff_data
        if buff_data is None:
            self.clear()
            self.setVisible(False)
            return
        pixmap = BuffIconManager.extract_icon_from_buff(buff_data, self.ICON_SIZE)
        if pixmap:
            self.setPixmap(pixmap)
        else:
            self.clear()
        self.setVisible(True)

    def get_buff(self) -> Optional[Dict[str, Any]]:
        return self._current_buff

    # ── 悬浮弹窗 ────────────────────────────────────────

    def enterEvent(self, event) -> None:
        if self._current_buff:
            name_key = self._current_buff.get("name_i18n_key", "")
            name = (
                tr(name_key, default=self._current_buff.get("name", ""))
                if name_key else self._current_buff.get("name", "")
            )
            desc_key = self._current_buff.get("desc_i18n_key", "")
            desc = (
                tr(desc_key, default=self._current_buff.get("desc", ""))
                if desc_key else self._current_buff.get("desc", "")
            )
            _get_popup().show_for(name=name, desc=desc, global_pos=QCursor.pos())
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        _get_popup().hide()
        super().leaveEvent(event)

    # 鼠标事件：accept 阻断传播，防止触发 PetWindow 拖动 ──────────

    def mousePressEvent(self, event) -> None:
        event.accept()  # 不传递给父级，图标区域不能拖动

    def mouseMoveEvent(self, event) -> None:
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
# 状态栏容器
# ─────────────────────────────────────────────────────────────────────────────

class BuffStatusBar(QWidget):
    """
    Buff 状态栏。

    竖向固定三个槽位（上→下），有 buff 时显示图标，无 buff 时槽位隐藏。
    容器自身透明且转发鼠标事件，不干扰宠物拖动。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._log_prefix = "[Life][Buff]"
        self.setFixedSize(32, 128)  # 固定尺寸，避免无图标时缩到 0
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.buff_icons: List[BuffStatusIcon] = []
        for _ in range(3):
            icon = BuffStatusIcon(self)
            self.buff_icons.append(icon)
            layout.addWidget(icon)

        layout.addStretch()

        self._displayed_buffs: List[Optional[Dict[str, Any]]] = [None, None, None]
        _log.DEBUG(f"{self._log_prefix} Buff 状态栏已初始化")

    # ── 公共接口 ─────────────────────────────────────────

    def set_buffs(self, buffs: List[Dict[str, Any]]) -> None:
        displayed = list(buffs[:3])
        while len(displayed) < 3:
            displayed.append(None)
        self._displayed_buffs = displayed
        for i, buff_data in enumerate(self._displayed_buffs):
            self.buff_icons[i].set_buff(buff_data)
        _log.DEBUG(f"{self._log_prefix} 显示 {sum(1 for b in displayed if b)} 个 buff")

    def clear_buffs(self) -> None:
        for icon in self.buff_icons:
            icon.set_buff(None)
        self._displayed_buffs = [None, None, None]
        _log.DEBUG(f"{self._log_prefix} 已清除 buff 显示")

    def update_buff_at(self, index: int, buff_data: Optional[Dict[str, Any]]) -> None:
        if not (0 <= index < 3):
            return
        self._displayed_buffs[index] = buff_data
        self.buff_icons[index].set_buff(buff_data)

    def get_displayed_buffs(self) -> List[Optional[Dict[str, Any]]]:
        return self._displayed_buffs.copy()

    # 鼠标事件：accept 阻断传播，防止触发 PetWindow 拖动 ────────

    def mousePressEvent(self, event) -> None:
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        event.accept()
