from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from ui.setting.common import create_section_card
from util.i18n import tr


class ValueHoverPopup(QFrame):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("valueHoverPopupRoot")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.panel = QFrame(self)
        self.panel.setObjectName("valueHoverPopup")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(10, 7, 10, 7)
        panel_layout.setSpacing(0)

        self.value_label = QLabel("0/0")
        self.value_label.setObjectName("valueLabel")
        panel_layout.addWidget(self.value_label)
        layout.addWidget(self.panel)

        self.setStyleSheet(
            """
            QFrame#valueHoverPopupRoot {
                background: transparent;
                border: none;
            }
            QFrame#valueHoverPopup {
                background-color: #1b1b1b;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
            }
            QLabel#valueLabel {
                color: #f3f3f3;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
                border: none;
            }
            """
        )

    def show_value(self, value_text: str, global_pos: QPoint) -> None:
        self.value_label.setText(value_text)
        self.adjustSize()
        self.move(global_pos + QPoint(14, 18))
        self.show()


class HoverDetailProgressBar(QProgressBar):
    """
    三段式进度条：
      蓝色  = 当前值
      灰色  = state_max 内的空余
      红色  = state_max 到 cap_max 之间被 buff 削减的部分
    """

    _COLOR_FILL_START = QColor("#3fbbff")
    _COLOR_FILL_END   = QColor("#0099ff")
    _COLOR_BG         = QColor("#1f1f1f")
    _COLOR_CAP_BLOCK  = QColor("#8b1a1a")   # 被削减掉的上限区域
    _RADIUS = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._detail = ""
        self.setMouseTracking(True)
        self._popup = ValueHoverPopup()
        self._value_ratio: float = 0.0     # value / cap_max  [0,1]
        self._cap_ratio: float = 1.0       # state_max / cap_max  [0,1]
        self.setTextVisible(False)

    def set_detail(self, detail: str) -> None:
        self._detail = detail

    def set_ratios(self, value_ratio: float, cap_ratio: float) -> None:
        self._value_ratio = max(0.0, min(1.0, value_ratio))
        self._cap_ratio   = max(0.0, min(1.0, cap_ratio))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        r = self.rect()
        pad = 2
        inner = r.adjusted(pad, pad, -pad, -pad)
        w = inner.width()
        h = inner.height()
        x0 = inner.x()
        y0 = inner.y()
        rad = self._RADIUS

        def clipped_rect(x: int, width: int) -> QRect:
            return QRect(x, y0, max(0, width), h)

        # 外边框背景
        path_outer = QPainterPath()
        path_outer.addRoundedRect(r, rad + pad, rad + pad)
        painter.fillPath(path_outer, QColor("#3a3a3a"))

        # 裁剪到内圆角区域
        clip_path = QPainterPath()
        clip_path.addRoundedRect(inner, rad, rad)
        painter.setClipPath(clip_path)

        # 1. 底层：全灰背景
        painter.fillRect(inner, self._COLOR_BG)

        # 3. 红色：被 buff 削减区域  (cap_ratio ~ 1.0)
        cap_blocked = 1.0 - self._cap_ratio
        if cap_blocked > 0.001:
            rx = x0 + int(self._cap_ratio * w)
            rw = w - int(self._cap_ratio * w)
            painter.fillRect(clipped_rect(rx, rw), self._COLOR_CAP_BLOCK)

        # 2. 蓝色渐变：当前值
        if self._value_ratio > 0.001:
            vw = max(1, int(self._value_ratio * w))
            from PySide6.QtGui import QLinearGradient
            grad = QLinearGradient(x0, 0, x0 + vw, 0)
            grad.setColorAt(0.0, self._COLOR_FILL_START)
            grad.setColorAt(1.0, self._COLOR_FILL_END)
            painter.fillRect(clipped_rect(x0, vw), grad)

        # 文字百分比（居中）
        pct_text = f"{int(round(self._value_ratio * 100))}%"
        painter.setClipping(False)
        pen_color = QColor("#ffffff")
        painter.setPen(pen_color)
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(r, Qt.AlignCenter, pct_text)

        painter.end()

    def _show_detail_popup(self, global_pos: QPoint | None = None) -> None:
        if not self._detail:
            return
        if global_pos is None:
            global_pos = self.mapToGlobal(self.rect().center())
        self._popup.show_value(self._detail, global_pos)

    def enterEvent(self, event):
        self._show_detail_popup(self.mapToGlobal(event.position().toPoint()))
        return super().enterEvent(event)

    def mouseMoveEvent(self, event):
        self._show_detail_popup(event.globalPosition().toPoint())
        return super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._popup.hide()
        return super().leaveEvent(event)

class LifeStatesTab(QFrame):
    tab_name = tr("life.tabs.states")

    def __init__(self, state_definitions: list[dict] | None = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        states_card = create_section_card(tr("life.states.card.title"), tr("life.states.card.desc"))
        card_layout = states_card.layout()

        self._state_defs = state_definitions or []
        self.progress_rows: dict[str, HoverDetailProgressBar] = {}
        for state_def in self._state_defs:
            state = str(state_def.get("id") or "").strip()
            if not state:
                continue

            i18n_key = str(state_def.get("i18n_key") or f"life.state.{state}")
            fallback_name = str(state_def.get("name") or state)

            row = QHBoxLayout()
            row.setSpacing(12)

            label = QLabel(tr(i18n_key, default=fallback_name))
            label.setObjectName("fieldLabel")
            label.setFixedWidth(88)
            row.addWidget(label)

            bar = HoverDetailProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(22)
            row.addWidget(bar, 1)

            card_layout.addLayout(row)
            self.progress_rows[state] = bar

        layout.addWidget(states_card)
        layout.addStretch()

    _MIN_VISIBLE_RATIO = 0.04  # 最小可见比例，防止圆角被截断

    def update_data(self, profile) -> None:
        cap_max = 1000.0  # 基础满值（固定量程）
        for state, bar in self.progress_rows.items():
            value = float(profile.states.get(state, 0.0))
            state_max = float(profile.state_max.get(state, cap_max))
            state_max = min(state_max, cap_max)  # 不超过基础满值

            value_ratio = max(0.0, min(1.0, value / cap_max))
            cap_ratio = max(0.0, min(1.0, state_max / cap_max))

            # 最小可见保护
            if 0 < value_ratio < self._MIN_VISIBLE_RATIO:
                value_ratio = self._MIN_VISIBLE_RATIO

            bar.set_ratios(value_ratio, cap_ratio)
            bar.set_detail(f"{int(round(value))}/{int(round(state_max))} (cap {int(round(cap_max))})")
