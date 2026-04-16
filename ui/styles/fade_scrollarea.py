"""带渐隐滚动条的 QScrollArea。

- 无可滚动内容时滚动条完全隐藏
- 滚动或鼠标悬浮时滚动条显示
- 停止操作后自动隐藏
- 垂直和水平滚动条各自独立控制

采用 stylesheet + 连续属性动画控制滚动条把柄透明度。
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, Property, QPropertyAnimation, QTimer, Qt
from PySide6.QtWidgets import QScrollArea, QWidget

_VBAR_BASE = (
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

_HBAR_BASE = (
    "QScrollBar:horizontal {"
    "  background-color: transparent; height: 8px; border: none;"
    "  margin: 1px 4px 1px 4px;"
    "}"
    "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {"
    "  border: none; background: none; width: 0px;"
    "}"
    "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {"
    "  background: transparent;"
    "}"
)


def _handle_color(alpha: float, hover_boost: float) -> tuple[str, str]:
    if alpha <= 0.001:
        return "transparent", "transparent"
    hover_alpha = min(1.0, alpha + hover_boost)
    return (f"rgba(245, 245, 245, {alpha:.3f})",
            f"rgba(245, 245, 245, {hover_alpha:.3f})")


class FadeScrollArea(QScrollArea):
    """滚动条自动渐隐的 QScrollArea，垂直/水平独立控制。"""

    FADE_OUT_DELAY_MS = 1500
    LEAVE_DELAY_MS = 800
    VISIBLE_ALPHA = 0.45
    HOVER_BOOST = 0.22
    FADE_IN_MS = 160
    FADE_OUT_MS = 520

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self._vbar = self.verticalScrollBar()
        self._hbar = self.horizontalScrollBar()

        # 独立 alpha
        self._v_alpha = 0.0
        self._h_alpha = 0.0
        self._v_hover = False
        self._h_hover = False
        self._mouse_inside = False

        # 独立动画
        self._v_anim = QPropertyAnimation(self, b"vAlpha", self)
        self._v_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._h_anim = QPropertyAnimation(self, b"hAlpha", self)
        self._h_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # 独立空闲定时器
        self._v_idle = QTimer(self)
        self._v_idle.setSingleShot(True)
        self._v_idle.timeout.connect(self._v_fade_out)

        self._h_idle = QTimer(self)
        self._h_idle.setSingleShot(True)
        self._h_idle.timeout.connect(self._h_fade_out)

        self._vbar.valueChanged.connect(self._on_vscroll_activity)
        self._vbar.rangeChanged.connect(self._on_vrange_changed)
        self._vbar.installEventFilter(self)

        self._hbar.valueChanged.connect(self._on_hscroll_activity)
        self._hbar.rangeChanged.connect(self._on_hrange_changed)
        self._hbar.installEventFilter(self)

        self._apply_v_style(0.0)
        self._apply_h_style(0.0)

    # ── helpers ─────────────────────────────────────

    def _has_vscroll(self) -> bool:
        return self._vbar.maximum() > self._vbar.minimum()

    def _has_hscroll(self) -> bool:
        return self._hbar.maximum() > self._hbar.minimum()

    # ── signals ─────────────────────────────────────

    def _on_vscroll_activity(self) -> None:
        if not self._has_vscroll():
            return
        self._v_fade_in()
        self._v_idle.start(self.FADE_OUT_DELAY_MS)

    def _on_hscroll_activity(self) -> None:
        if not self._has_hscroll():
            return
        self._h_fade_in()
        self._h_idle.start(self.FADE_OUT_DELAY_MS)

    def _on_vrange_changed(self, min_val: int, max_val: int) -> None:
        if max_val <= min_val:
            self._v_idle.stop()
            self._v_animate_to(0.0, 80)
            return
        if self._mouse_inside or self._v_hover:
            self._v_fade_in()
            self._v_idle.start(self.FADE_OUT_DELAY_MS)

    def _on_hrange_changed(self, min_val: int, max_val: int) -> None:
        if max_val <= min_val:
            self._h_idle.stop()
            self._h_animate_to(0.0, 80)
            return
        if self._mouse_inside or self._h_hover:
            self._h_fade_in()
            self._h_idle.start(self.FADE_OUT_DELAY_MS)

    # ── show / hide (vertical) ──────────────────────

    def _v_animate_to(self, target: float, duration_ms: int) -> None:
        self._v_anim.stop()
        self._v_anim.setDuration(duration_ms)
        self._v_anim.setStartValue(self._v_alpha)
        self._v_anim.setEndValue(max(0.0, min(1.0, target)))
        self._v_anim.start()

    def _v_fade_in(self) -> None:
        self._v_animate_to(self.VISIBLE_ALPHA, self.FADE_IN_MS)

    def _v_fade_out(self) -> None:
        if self._v_hover:
            self._v_idle.start(self.FADE_OUT_DELAY_MS)
            return
        self._v_animate_to(0.0, self.FADE_OUT_MS)

    # ── show / hide (horizontal) ────────────────────

    def _h_animate_to(self, target: float, duration_ms: int) -> None:
        self._h_anim.stop()
        self._h_anim.setDuration(duration_ms)
        self._h_anim.setStartValue(self._h_alpha)
        self._h_anim.setEndValue(max(0.0, min(1.0, target)))
        self._h_anim.start()

    def _h_fade_in(self) -> None:
        self._h_animate_to(self.VISIBLE_ALPHA, self.FADE_IN_MS)

    def _h_fade_out(self) -> None:
        if self._h_hover:
            self._h_idle.start(self.FADE_OUT_DELAY_MS)
            return
        self._h_animate_to(0.0, self.FADE_OUT_MS)

    # ── style ───────────────────────────────────────

    def _apply_v_style(self, alpha: float) -> None:
        color, hover_color = _handle_color(alpha, self.HOVER_BOOST)
        self._vbar.setStyleSheet(
            _VBAR_BASE +
            "QScrollBar::handle:vertical {"
            f"  background-color: {color}; border-radius: 3px; min-height: 28px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            f"  background-color: {hover_color};"
            "}"
        )

    def _apply_h_style(self, alpha: float) -> None:
        color, hover_color = _handle_color(alpha, self.HOVER_BOOST)
        self._hbar.setStyleSheet(
            _HBAR_BASE +
            "QScrollBar::handle:horizontal {"
            f"  background-color: {color}; border-radius: 3px; min-width: 28px;"
            "}"
            "QScrollBar::handle:horizontal:hover {"
            f"  background-color: {hover_color};"
            "}"
        )

    # ── Qt properties for animation ─────────────────

    def _get_v_alpha(self) -> float:
        return self._v_alpha

    def _set_v_alpha(self, value: float) -> None:
        self._v_alpha = max(0.0, min(1.0, float(value)))
        self._apply_v_style(self._v_alpha)

    vAlpha = Property(float, _get_v_alpha, _set_v_alpha)

    def _get_h_alpha(self) -> float:
        return self._h_alpha

    def _set_h_alpha(self, value: float) -> None:
        self._h_alpha = max(0.0, min(1.0, float(value)))
        self._apply_h_style(self._h_alpha)

    hAlpha = Property(float, _get_h_alpha, _set_h_alpha)

    # ── event filter ────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        if not hasattr(self, "_vbar") or not hasattr(self, "_hbar"):
            return super().eventFilter(obj, event)
        et = event.type()
        if obj is self._vbar:
            if et in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
                self._v_hover = True
                if self._has_vscroll():
                    self._v_fade_in()
                    self._v_idle.start(self.FADE_OUT_DELAY_MS)
            elif et in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                self._v_hover = False
                if self._v_alpha > 0:
                    self._v_idle.start(self.LEAVE_DELAY_MS)
            elif et in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.Wheel):
                if self._has_vscroll():
                    self._v_fade_in()
                    self._v_idle.start(self.FADE_OUT_DELAY_MS)
            elif et == QEvent.Type.MouseButtonRelease:
                if self._v_alpha > 0:
                    self._v_idle.start(self.LEAVE_DELAY_MS)
        elif obj is self._hbar:
            if et in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
                self._h_hover = True
                if self._has_hscroll():
                    self._h_fade_in()
                    self._h_idle.start(self.FADE_OUT_DELAY_MS)
            elif et in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                self._h_hover = False
                if self._h_alpha > 0:
                    self._h_idle.start(self.LEAVE_DELAY_MS)
            elif et in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.Wheel):
                if self._has_hscroll():
                    self._h_fade_in()
                    self._h_idle.start(self.FADE_OUT_DELAY_MS)
            elif et == QEvent.Type.MouseButtonRelease:
                if self._h_alpha > 0:
                    self._h_idle.start(self.LEAVE_DELAY_MS)
        return super().eventFilter(obj, event)

    # ── mouse events ────────────────────────────────

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._mouse_inside = True
        if self._has_vscroll():
            self._v_fade_in()
            self._v_idle.start(self.FADE_OUT_DELAY_MS)
        if self._has_hscroll():
            self._h_fade_in()
            self._h_idle.start(self.FADE_OUT_DELAY_MS)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._mouse_inside = False
        if self._v_alpha > 0:
            self._v_idle.start(self.LEAVE_DELAY_MS)
        if self._h_alpha > 0:
            self._h_idle.start(self.LEAVE_DELAY_MS)

    def wheelEvent(self, event) -> None:
        super().wheelEvent(event)
        if self._has_vscroll():
            self._v_fade_in()
            self._v_idle.start(self.FADE_OUT_DELAY_MS)
        if self._has_hscroll():
            self._h_fade_in()
            self._h_idle.start(self.FADE_OUT_DELAY_MS)
