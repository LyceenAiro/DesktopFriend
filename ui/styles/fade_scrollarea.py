"""带渐隐滚动条的 QScrollArea。

- 无可滚动内容时滚动条完全隐藏
- 滚动或鼠标悬浮时滚动条显示
- 停止操作后自动隐藏

采用 stylesheet + 连续属性动画控制滚动条把柄透明度。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, Property, QPropertyAnimation, QTimer, Qt
from PySide6.QtWidgets import QScrollArea, QWidget

# 可见/隐藏把柄样式模板
# 滚动条轨道（始终透明，不影响布局）
_BAR_BASE = (
    "QScrollBar:vertical {"
    "  background-color: transparent; width: 8px; border: none;"
    "  margin: 4px 1px 4px 1px;"
    "}"
    "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
    "  border: none; background: none; height: 0px;"
    "}"
    "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
    "  background: transparent;"
    "}"
)


class FadeScrollArea(QScrollArea):
    """滚动条自动渐隐的 QScrollArea。"""

    FADE_OUT_DELAY_MS = 1500
    LEAVE_DELAY_MS = 800
    VISIBLE_ALPHA = 0.45
    HOVER_BOOST = 0.22
    FADE_IN_MS = 160
    FADE_OUT_MS = 520

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._vbar = self.verticalScrollBar()
        self._handle_alpha = 0.0
        self._bar_hover = False
        self._mouse_inside = False

        self._anim = QPropertyAnimation(self, b"handleAlpha", self)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # 空闲定时器：停止滚动后触发渐隐
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._fade_out)

        self._vbar.valueChanged.connect(self._on_scroll_activity)
        self._vbar.rangeChanged.connect(self._on_range_changed)
        self._vbar.installEventFilter(self)

        # 初始隐藏
        self._apply_bar_style(0.0)

    # ── signals ─────────────────────────────────────

    def _on_scroll_activity(self) -> None:
        if self._vbar.maximum() <= self._vbar.minimum():
            return
        self._fade_in()
        self._reset_idle(self.FADE_OUT_DELAY_MS)

    def _on_range_changed(self, min_val: int, max_val: int) -> None:
        if max_val <= min_val:
            self._idle_timer.stop()
            self._animate_to(0.0, 80)
            return
        if self._mouse_inside or self._bar_hover:
            self._fade_in()
            self._reset_idle(self.FADE_OUT_DELAY_MS)

    # ── show / hide ─────────────────────────────────

    def _animate_to(self, target: float, duration_ms: int) -> None:
        self._anim.stop()
        self._anim.setDuration(duration_ms)
        self._anim.setStartValue(self._handle_alpha)
        self._anim.setEndValue(max(0.0, min(1.0, target)))
        self._anim.start()

    def _fade_in(self) -> None:
        self._animate_to(self.VISIBLE_ALPHA, self.FADE_IN_MS)

    def _fade_out(self) -> None:
        if self._bar_hover:
            self._reset_idle(self.FADE_OUT_DELAY_MS)
            return
        self._animate_to(0.0, self.FADE_OUT_MS)

    def _reset_idle(self, delay_ms: int) -> None:
        self._idle_timer.start(delay_ms)

    def _apply_bar_style(self, alpha: float) -> None:
        if alpha <= 0.001:
            color = "transparent"
            hover_color = "transparent"
        else:
            hover_alpha = min(1.0, alpha + self.HOVER_BOOST)
            color = f"rgba(245, 245, 245, {alpha:.3f})"
            hover_color = f"rgba(245, 245, 245, {hover_alpha:.3f})"
        handle_style = (
            "QScrollBar::handle:vertical {"
            f"  background-color: {color}; border-radius: 3px; min-height: 28px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            f"  background-color: {hover_color};"
            "}"
        )
        self._vbar.setStyleSheet(_BAR_BASE + handle_style)

    def _get_handle_alpha(self) -> float:
        return self._handle_alpha

    def _set_handle_alpha(self, value: float) -> None:
        self._handle_alpha = max(0.0, min(1.0, float(value)))
        self._apply_bar_style(self._handle_alpha)

    handleAlpha = Property(float, _get_handle_alpha, _set_handle_alpha)

    def eventFilter(self, obj, event) -> bool:
        if not hasattr(self, "_vbar"):
            return super().eventFilter(obj, event)
        if obj is self._vbar:
            et = event.type()
            if et in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
                self._bar_hover = True
                if self._vbar.maximum() > self._vbar.minimum():
                    self._fade_in()
                    self._reset_idle(self.FADE_OUT_DELAY_MS)
            elif et in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                self._bar_hover = False
                if self._handle_alpha > 0:
                    self._reset_idle(self.LEAVE_DELAY_MS)
            elif et in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.Wheel):
                if self._vbar.maximum() > self._vbar.minimum():
                    self._fade_in()
                    self._reset_idle(self.FADE_OUT_DELAY_MS)
            elif et == QEvent.Type.MouseButtonRelease:
                if self._handle_alpha > 0:
                    self._reset_idle(self.LEAVE_DELAY_MS)
        return super().eventFilter(obj, event)

    # ── mouse events ────────────────────────────────

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._mouse_inside = True
        if self._vbar.maximum() > self._vbar.minimum():
            self._fade_in()
            self._reset_idle(self.FADE_OUT_DELAY_MS)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._mouse_inside = False
        if self._handle_alpha > 0:
            self._reset_idle(self.LEAVE_DELAY_MS)

    def wheelEvent(self, event) -> None:
        super().wheelEvent(event)
        if self._vbar.maximum() > self._vbar.minimum():
            self._fade_in()
            self._reset_idle(self.FADE_OUT_DELAY_MS)
