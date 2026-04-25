"""
Buff 状态显示栏

在宠物右侧竖向显示三个 buff 状态图标（32x32），固定三个位置。
当 buff 数量超过 3 个时，第三个图标变为 "..." 溢出指示器。
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor, QPainter, QPixmap, QColor
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from util.buff_icon_manager import BuffIconManager
from util.i18n import tr
from util.log import _log


# ─────────────────────────────────────────────────────────────────────────────
# "..." 溢出图标
# ─────────────────────────────────────────────────────────────────────────────

_DOTS_PIXMAP_CACHE: Optional[QPixmap] = None


def _get_dots_pixmap(size: int = 32) -> QPixmap:
    global _DOTS_PIXMAP_CACHE
    if _DOTS_PIXMAP_CACHE is not None and not _DOTS_PIXMAP_CACHE.isNull():
        return _DOTS_PIXMAP_CACHE
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # fill full area with nearly-invisible background so the entire
    # 32×32 rect registers mouse events
    painter.fillRect(0, 0, size, size, QColor(0, 0, 0, 1))

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#8ec8ff"))
    dot_r = 2.5
    gap = 5
    total_w = 3 * dot_r * 2 + 2 * gap
    sx = (size - total_w) / 2.0 + dot_r
    cy = size / 2.0
    for i in range(3):
        cx = sx + i * (dot_r * 2 + gap)
        painter.drawEllipse(int(cx - dot_r), int(cy - dot_r), int(dot_r * 2), int(dot_r * 2))
    painter.end()
    _DOTS_PIXMAP_CACHE = pixmap
    return pixmap


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

        self.effects_label = QLabel()
        self.effects_label.setObjectName("detailLabel")
        self.effects_label.setWordWrap(True)
        self.effects_label.setMaximumWidth(200)
        self.effects_label.setVisible(False)
        panel_layout.addWidget(self.effects_label)

        self.caps_label = QLabel()
        self.caps_label.setObjectName("detailLabel")
        self.caps_label.setWordWrap(True)
        self.caps_label.setMaximumWidth(200)
        self.caps_label.setVisible(False)
        panel_layout.addWidget(self.caps_label)

        # 溢出列表标签（多 buff 列表展示）
        self.list_label = QLabel()
        self.list_label.setObjectName("detailLabel")
        self.list_label.setWordWrap(True)
        self.list_label.setMaximumWidth(260)
        self.list_label.setVisible(False)
        panel_layout.addWidget(self.list_label)

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

    def show_for(self, *, name: str, desc: str, effects_text: str, caps_text: str, global_pos: QPoint) -> None:
        self.list_label.setVisible(False)
        self.name_label.setText(name)
        self.desc_label.setText(desc)
        self.desc_label.setVisible(bool(desc))
        if effects_text:
            self.effects_label.setText(effects_text)
            self.effects_label.setVisible(True)
        else:
            self.effects_label.setVisible(False)
        if caps_text:
            self.caps_label.setText(caps_text)
            self.caps_label.setVisible(True)
        else:
            self.caps_label.setVisible(False)
        self.adjustSize()
        self.move(global_pos + QPoint(14, 18))
        self.show()

    def show_overflow(self, buffs: List[Dict[str, Any]], global_pos: QPoint, show_desc: bool = True) -> None:
        self.name_label.setText(tr("life.buff.popup.overflow_title"))
        self.desc_label.setVisible(False)
        self.effects_label.setVisible(False)
        self.caps_label.setVisible(False)

        lines: list[str] = []
        for buff in buffs:
            name_key = buff.get("name_i18n_key", "")
            name = (
                tr(name_key, default=buff.get("name", ""))
                if name_key else buff.get("name", "")
            )
            lines.append(f"• {name}")
            if show_desc:
                desc_key = buff.get("desc_i18n_key", "")
                desc = (
                    tr(desc_key, default=buff.get("desc", ""))
                    if desc_key else buff.get("desc", "")
                )
                if desc:
                    lines.append(f"  {desc}")

        self.list_label.setText("\n".join(lines))
        self.list_label.setVisible(True)
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
        self._overflow_mode: bool = False
        self._overflow_buffs: List[Dict[str, Any]] = []
        self.setVisible(False)

    # ── 数据设置 ────────────────────────────────────────

    def set_buff(self, buff_data: Optional[Dict[str, Any]]) -> None:
        self._overflow_mode = False
        self._overflow_buffs = []
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

    def set_overflow(self, all_buffs: List[Dict[str, Any]]) -> None:
        self._overflow_mode = True
        self._overflow_buffs = all_buffs
        self._current_buff = None
        self.setPixmap(_get_dots_pixmap(self.ICON_SIZE))
        self.setVisible(True)

    def get_buff(self) -> Optional[Dict[str, Any]]:
        return self._current_buff

    # ── 悬浮弹窗 ────────────────────────────────────────

    def enterEvent(self, event) -> None:
        if self._overflow_mode and self._overflow_buffs:
            _get_popup().show_overflow(self._overflow_buffs, QCursor.pos(), show_desc=False)
        elif self._current_buff:
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

            from util.cfg import load_config
            _cfg = load_config("debug")
            dev_mode = bool(_cfg.get("developer_mode", False))

            effects_text = ""
            caps_text = ""
            if dev_mode:
                effects_parts: list[str] = []
                caps_parts: list[str] = []
                try:
                    from module.life.runtime import get_life_system
                    ls = get_life_system()
                    if ls is not None:
                        state_keys = ls.state_keys
                        nutrition_keys = ls.nutrition_keys
                        known_keys = set(state_keys) | set(nutrition_keys)
                        for key, value in self._current_buff.items():
                            if isinstance(value, (int, float)):
                                if key.endswith("s") and key[:-1] in state_keys:
                                    effects_parts.append(f"{key[:-1]}: {value:+.2f}")
                                elif key.endswith("s") and key[:-1] in nutrition_keys:
                                    effects_parts.append(f"{key[:-1]}: {value:+.2f}")
                            if isinstance(value, (int, float, str)):
                                if key.endswith("_max") and key[:-4] in known_keys:
                                    caps_parts.append(f"{key}: {value}")
                                elif key.endswith("_min") and key[:-4] in known_keys:
                                    caps_parts.append(f"{key}: {value}")
                                elif key.endswith("_max2") and key[:-5] in known_keys:
                                    caps_parts.append(f"{key}: {value}")
                except Exception:
                    pass

                effects_text = tr("life.buff.popup.effects", text=", ".join(effects_parts)) if effects_parts else ""
                caps_text = tr("life.buff.popup.caps", text=", ".join(caps_parts)) if caps_parts else ""

            _get_popup().show_for(
                name=name, desc=desc,
                effects_text=effects_text,
                caps_text=caps_text,
                global_pos=QCursor.pos(),
            )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        _get_popup().hide()
        super().leaveEvent(event)

    # 鼠标事件：accept 阻断传播，防止触发 PetWindow 拖动 ──────────

    def mousePressEvent(self, event) -> None:
        event.accept()  # 不传递给父级，图标区域不能拖动

    def mouseMoveEvent(self, event) -> None:
        popup = _get_popup()
        if popup.isVisible():
            popup.move(QCursor.pos() + QPoint(14, 18))
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
        if len(buffs) > 3:
            for i in range(2):
                self.buff_icons[i].set_buff(buffs[i])
            self.buff_icons[2].set_overflow(buffs)
            self._displayed_buffs = buffs[:2] + [buffs[2] if len(buffs) > 2 else None]
        else:
            displayed = list(buffs[:3])
            while len(displayed) < 3:
                displayed.append(None)
            self._displayed_buffs = displayed
            for i, buff_data in enumerate(self._displayed_buffs):
                self.buff_icons[i].set_buff(buff_data)
        _log.DEBUG(f"{self._log_prefix} 显示 {sum(1 for b in buffs if b)} 个 buff")

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
