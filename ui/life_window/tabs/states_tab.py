from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
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
        panel_layout.setContentsMargins(12, 10, 12, 10)
        panel_layout.setSpacing(4)

        self.title_label = QLabel("STATE")
        self.title_label.setObjectName("titleLabel")
        panel_layout.addWidget(self.title_label)

        self.value_label = QLabel("0 / 0")
        self.value_label.setObjectName("valueLabel")
        panel_layout.addWidget(self.value_label)

        self.tick_label = QLabel("tick: +0.00")
        self.tick_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.tick_label)

        self.cap_label = QLabel("cap: +0.00")
        self.cap_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.cap_label)

        self.percent_label = QLabel("percent: +0.00%")
        self.percent_label.setObjectName("detailLabel")
        panel_layout.addWidget(self.percent_label)

        layout.addWidget(self.panel)

        self.setStyleSheet(
            """
            QFrame#valueHoverPopupRoot {
                background: transparent;
                border: none;
            }
            QFrame#valueHoverPopup {
                background-color: #111820;
                border: 1px solid #2e4d6b;
                border-radius: 10px;
            }
            QLabel#titleLabel {
                color: #8ec8ff;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
                background: transparent;
                border: none;
            }
            QLabel#valueLabel {
                color: #f7fbff;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
                border: none;
            }
            QLabel#detailLabel {
                color: #b9d7ee;
                font-size: 11px;
                background: transparent;
                border: none;
            }
            """
        )

    def show_value(
        self,
        *,
        title: str,
        value_text: str,
        tick_text: str,
        cap_text: str,
        percent_text: str,
        global_pos: QPoint,
    ) -> None:
        self.title_label.setText(title)
        self.value_label.setText(value_text)
        self.tick_label.setText(tick_text)
        self.cap_label.setText(cap_text)
        self.percent_label.setText(percent_text)
        self.adjustSize()
        self.move(global_pos + QPoint(14, 18))
        self.show()


class HoverDetailProgressBar(QProgressBar):
    _COLOR_FILL_START = QColor("#3fbbff")
    _COLOR_FILL_END = QColor("#0099ff")
    _COLOR_OVERFLOW_FILL_START = QColor("#ffcf5a")
    _COLOR_OVERFLOW_FILL_END = QColor("#ff8f1f")
    _COLOR_BG = QColor("#1f1f1f")
    _COLOR_CAP_BLOCK = QColor("#8b1a1a")
    _RADIUS = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._detail: dict[str, Any] = {}
        self._legacy_detail_text: str = ""
        self._legacy_tick_delta: float = 0.0
        self._legacy_fixed_delta: float = 0.0
        self._legacy_percent_delta: float = 0.0
        self._legacy_percent_value: float = 0.0
        self.setMouseTracking(True)
        self._popup = ValueHoverPopup()
        self._last_global_pos: QPoint = QPoint()
        self._base_fill_ratio: float = 0.0
        self._base_cap_ratio: float = 1.0
        self._overflow_enabled = False
        self._overflow_fill_ratio: float = 0.0
        self._display_percent: int = 0
        self.setTextVisible(False)

    # 兼容旧调用方（如 nutrition_tab）
    def set_ratios(self, value_ratio: float, cap_ratio: float) -> None:
        self._base_fill_ratio = max(0.0, min(1.0, float(value_ratio)))
        self._base_cap_ratio = max(0.0, min(1.0, float(cap_ratio)))
        self._overflow_enabled = False
        self._overflow_fill_ratio = 0.0
        self._display_percent = int(round(max(0.0, float(value_ratio)) * 100))
        self.update()

    # 兼容旧调用方（如 nutrition_tab）
    def set_detail(self, detail: str) -> None:
        self._legacy_detail_text = str(detail)

    # 兼容旧调用方（如 nutrition_tab）
    def set_legacy_metrics(
        self,
        *,
        tick_delta: float = 0.0,
        fixed_delta: float = 0.0,
        percent_delta: float = 0.0,
        percent_value: float = 0.0,
    ) -> None:
        self._legacy_tick_delta = float(tick_delta)
        self._legacy_fixed_delta = float(fixed_delta)
        self._legacy_percent_delta = float(percent_delta)
        self._legacy_percent_value = float(percent_value)
        self._refresh_popup_if_visible()

    def _refresh_popup_if_visible(self) -> None:
        if self._popup.isVisible() and not self._last_global_pos.isNull():
            self._show_detail_popup(self._last_global_pos)

    def set_state_payload(self, payload: dict[str, Any]) -> None:
        self._detail = dict(payload)

        value = float(payload.get("value", 0.0))
        base_max = max(1.0, float(payload.get("base_max", 1000.0)))
        current_max = max(1.0, float(payload.get("max", base_max)))

        self._base_fill_ratio = max(0.0, min(1.0, min(value, base_max) / base_max))
        self._base_cap_ratio = max(0.0, min(1.0, current_max / base_max))
        self._display_percent = int(round(max(0.0, value / base_max) * 100))

        overflow_span = max(0.0, current_max - base_max)
        self._overflow_enabled = overflow_span > 0.001
        if self._overflow_enabled:
            overflow_value = max(0.0, value - base_max)
            self._overflow_fill_ratio = max(0.0, min(1.0, overflow_value / overflow_span))
        else:
            self._overflow_fill_ratio = 0.0

        self.update()
        self._refresh_popup_if_visible()

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

        path_outer = QPainterPath()
        path_outer.addRoundedRect(r, rad + pad, rad + pad)
        painter.fillPath(path_outer, QColor("#3a3a3a"))

        clip_path = QPainterPath()
        clip_path.addRoundedRect(inner, rad, rad)
        painter.setClipPath(clip_path)

        painter.fillRect(inner, self._COLOR_BG)

        cap_blocked = 1.0 - self._base_cap_ratio
        if cap_blocked > 0.001:
            rx = x0 + int(self._base_cap_ratio * w)
            rw = w - int(self._base_cap_ratio * w)
            painter.fillRect(clipped_rect(rx, rw), self._COLOR_CAP_BLOCK)

        if self._base_fill_ratio > 0.001:
            vw = max(1, int(self._base_fill_ratio * w))
            grad = QLinearGradient(x0, 0, x0 + vw, 0)
            grad.setColorAt(0.0, self._COLOR_FILL_START)
            grad.setColorAt(1.0, self._COLOR_FILL_END)
            painter.fillRect(clipped_rect(x0, vw), grad)

        if self._overflow_enabled:
            stripe_h = h
            stripe_y = y0
            stripe = QRect(x0, stripe_y, max(0, w), max(0, stripe_h))
            stripe_radius = min(4, stripe.height() // 2)

            if self._overflow_fill_ratio > 0.001 and stripe.width() > 0:
                sw = max(1, int(self._overflow_fill_ratio * stripe.width()))
                fill_rect = QRect(stripe.x(), stripe.y(), min(sw, stripe.width()), stripe.height())
                overflow_fill = QPainterPath()
                overflow_fill.addRoundedRect(fill_rect, stripe_radius, stripe_radius)
                overflow_grad = QLinearGradient(fill_rect.x(), fill_rect.y(), fill_rect.x() + fill_rect.width(), fill_rect.y())
                overflow_grad.setColorAt(0.0, self._COLOR_OVERFLOW_FILL_START)
                overflow_grad.setColorAt(1.0, self._COLOR_OVERFLOW_FILL_END)
                painter.fillPath(overflow_fill, overflow_grad)

        pct_text = f"{self._display_percent}%"
        painter.setClipping(False)
        painter.setPen(QColor("#ffffff"))
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(r, Qt.AlignCenter, pct_text)

        painter.end()

    def _show_detail_popup(self, global_pos: QPoint | None = None) -> None:
        if not self._detail and not self._legacy_detail_text:
            return
        if global_pos is None:
            global_pos = self.mapToGlobal(self.rect().center())

        if not self._detail:
            self._popup.show_value(
                title=tr("life.popup.legacy.title", default="数值"),
                value_text=self._legacy_detail_text,
                tick_text=tr("life.states.popup.tick", delta=f"{self._legacy_tick_delta:+.2f}"),
                cap_text=tr("life.states.popup.cap_flat", delta=f"{self._legacy_fixed_delta:+.0f}"),
                percent_text=tr(
                    "life.states.popup.cap_percent",
                    percent=f"{self._legacy_percent_delta:+.2f}%",
                    value=f"{self._legacy_percent_value:+.0f}",
                ),
                global_pos=global_pos,
            )
            return

        title = str(self._detail.get("name", "STATE")).upper()
        value = float(self._detail.get("value", 0.0))
        cur_min = float(self._detail.get("min", 0.0))
        cur_max = float(self._detail.get("max", 0.0))
        base_max = float(self._detail.get("base_max", 1000.0))
        tick_delta = float(self._detail.get("tick_delta", 0.0))
        max_fixed_delta = float(self._detail.get("max_fixed_delta", 0.0))
        max_percent_net = float(self._detail.get("max_percent_net", 0.0))
        max_percent_value = float(self._detail.get("max_percent_value_delta", 0.0))

        self._popup.show_value(
            title=title,
            value_text=tr(
                "life.states.popup.value",
                value=f"{value:.0f}",
                cur_max=f"{cur_max:.0f}",
                base_max=f"{base_max:.0f}",
            ),
            tick_text=tr("life.states.popup.tick", delta=f"{tick_delta:+.2f}"),
            cap_text=tr("life.states.popup.cap_flat", delta=f"{max_fixed_delta:+.0f}"),
            percent_text=tr(
                "life.states.popup.cap_percent",
                percent=f"{max_percent_net:+.2f}%",
                value=f"{max_percent_value:+.0f}",
            ),
            global_pos=global_pos,
        )

    def enterEvent(self, event):
        self._last_global_pos = self.mapToGlobal(event.position().toPoint())
        self._show_detail_popup(self._last_global_pos)
        return super().enterEvent(event)

    def mouseMoveEvent(self, event):
        self._last_global_pos = event.globalPosition().toPoint()
        self._show_detail_popup(self._last_global_pos)
        return super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._popup.hide()
        return super().leaveEvent(event)


class LifeStatesTab(QFrame):
    tab_name = tr("life.tabs.states")

    def __init__(
        self,
        state_definitions: list[dict] | None = None,
        get_state_runtime_snapshot: Callable[[], list[dict[str, Any]]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        states_card = create_section_card(tr("life.states.card.title"), tr("life.states.card.desc"))
        card_layout = states_card.layout()

        self._state_defs = state_definitions or []
        self._get_state_runtime_snapshot = get_state_runtime_snapshot
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

    def update_data(self, profile) -> None:
        runtime_rows: dict[str, dict[str, Any]] = {}
        if self._get_state_runtime_snapshot is not None:
            try:
                runtime_rows = {str(row.get("id", "")): dict(row) for row in self._get_state_runtime_snapshot()}
            except Exception:
                runtime_rows = {}

        for state, bar in self.progress_rows.items():
            row = runtime_rows.get(state)
            if row is None:
                base_max = float(profile.state_max.get(state, 1000.0))
                value = float(profile.states.get(state, 0.0))
                row = {
                    "id": state,
                    "name": tr(f"life.state.{state}", default=state),
                    "value": value,
                    "min": float(profile.state_min.get(state, 0.0)),
                    "max": float(profile.state_max.get(state, base_max)),
                    "base_max": base_max,
                    "tick_delta": 0.0,
                    "max_flat_delta": 0.0,
                    "max_percent_add": 0.0,
                    "max_percent_sub": 0.0,
                }

            bar.set_state_payload(row)
