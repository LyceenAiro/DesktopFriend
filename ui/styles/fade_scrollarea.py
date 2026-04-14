"""带渐隐滚动条的 QScrollArea。

- 无可滚动内容时滚动条完全隐藏
- 滚动或鼠标悬浮时滚动条显示
- 停止操作后自动隐藏

采用 stylesheet 方式控制滚动条把柄颜色透明度，避免 QGraphicsOpacityEffect 不可靠问题。
用定时器分步模拟渐隐效果。
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QScrollArea, QWidget

# 可见/隐藏把柄样式模板
_HANDLE_VISIBLE = (
    "QScrollBar::handle:vertical {"
    "  background-color: rgba(245, 245, 245, 0.45);"
    "  border-radius: 3px; min-height: 28px;"
    "}"
    "QScrollBar::handle:vertical:hover {"
    "  background-color: rgba(245, 245, 245, 0.7);"
    "}"
)
_HANDLE_HIDDEN = (
    "QScrollBar::handle:vertical {"
    "  background-color: transparent;"
    "  border-radius: 3px; min-height: 28px;"
    "}"
    "QScrollBar::handle:vertical:hover {"
    "  background-color: transparent;"
    "}"
)
_FADE_STEPS = [
    "rgba(245, 245, 245, 0.35)",
    "rgba(245, 245, 245, 0.25)",
    "rgba(245, 245, 245, 0.15)",
    "rgba(245, 245, 245, 0.06)",
    "transparent",
]

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
    FADE_STEP_MS = 80

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._vbar = self.verticalScrollBar()
        self._visible = False
        self._fading = False
        self._fade_step = 0

        # 空闲定时器：停止滚动后触发渐隐
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._start_fade_out)

        # 渐隐步进定时器
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(self.FADE_STEP_MS)
        self._fade_timer.timeout.connect(self._fade_step_tick)

        self._vbar.valueChanged.connect(self._on_scroll_activity)
        self._vbar.rangeChanged.connect(self._on_range_changed)

        # 初始隐藏
        self._apply_hidden()

    # ── signals ─────────────────────────────────────

    def _on_scroll_activity(self) -> None:
        if self._vbar.maximum() <= self._vbar.minimum():
            return
        self._show_bar()

    def _on_range_changed(self, min_val: int, max_val: int) -> None:
        if max_val <= min_val:
            self._cancel_all()
            self._apply_hidden()
        elif self._visible:
            self._reset_idle()

    # ── show / hide ─────────────────────────────────

    def _show_bar(self) -> None:
        self._cancel_fade()
        if not self._visible:
            self._visible = True
            self._apply_visible()
        self._reset_idle()

    def _reset_idle(self) -> None:
        self._idle_timer.start(self.FADE_OUT_DELAY_MS)

    def _cancel_fade(self) -> None:
        self._fading = False
        self._fade_timer.stop()

    def _cancel_all(self) -> None:
        self._idle_timer.stop()
        self._cancel_fade()
        self._visible = False

    def _start_fade_out(self) -> None:
        self._fading = True
        self._fade_step = 0
        self._fade_timer.start()

    def _fade_step_tick(self) -> None:
        if self._fade_step >= len(_FADE_STEPS):
            self._fade_timer.stop()
            self._fading = False
            self._visible = False
            self._apply_hidden()
            return
        color = _FADE_STEPS[self._fade_step]
        handle_style = (
            f"QScrollBar::handle:vertical {{"
            f"  background-color: {color}; border-radius: 3px; min-height: 28px;"
            f"}}"
            f"QScrollBar::handle:vertical:hover {{"
            f"  background-color: {color};"
            f"}}"
        )
        self._vbar.setStyleSheet(_BAR_BASE + handle_style)
        self._fade_step += 1

    def _apply_visible(self) -> None:
        self._vbar.setStyleSheet(_BAR_BASE + _HANDLE_VISIBLE)

    def _apply_hidden(self) -> None:
        self._vbar.setStyleSheet(_BAR_BASE + _HANDLE_HIDDEN)

    # ── mouse events ────────────────────────────────

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        if self._vbar.maximum() > self._vbar.minimum():
            self._show_bar()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        if self._visible:
            self._idle_timer.start(800)

    def wheelEvent(self, event) -> None:
        super().wheelEvent(event)
        if self._vbar.maximum() > self._vbar.minimum():
            self._show_bar()
