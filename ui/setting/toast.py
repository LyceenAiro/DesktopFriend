from typing import Optional

from PySide6.QtCore import QEasingCurve, QPoint, Property, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout


class ScrollingLabel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusToastLabel")
        self._max_content_width = 160
        self.setMaximumWidth(self._max_content_width)
        self.setMinimumWidth(1)
        self.setFixedWidth(1)
        self.setFixedHeight(16)
        self.setStyleSheet("QFrame#statusToastLabel { border: none; background: transparent; }")

        self._full_text = ""
        self._text_color = QColor("#ffffff")
        self._text_width = 0
        self._scroll_offset = 0
        self._scroll_range = 0
        self._edge_buffer_px = 16
        self._edge_pause_ms = 1000
        self._scroll_anim: Optional[QPropertyAnimation] = None
        self._reverse_anim: Optional[QPropertyAnimation] = None
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._start_scroll_animation)
        self._edge_pause_timer = QTimer(self)
        self._edge_pause_timer.setSingleShot(True)
        self._edge_pause_timer.timeout.connect(self._on_edge_pause_timeout)
        self._resume_reverse = False

    def set_max_content_width(self, width: int):
        self._max_content_width = max(32, int(width))
        self.setMaximumWidth(self._max_content_width)

    def set_text_color(self, color_hex: str):
        self._text_color = QColor(color_hex)
        self.update()

    def setText(self, text: str):
        self._full_text = text
        self._text_width = self.fontMetrics().horizontalAdvance(self._full_text)
        target_width = min(self._max_content_width, max(1, self._text_width))
        self.setFixedWidth(target_width)
        self.stop_scroll()
        self._set_scroll_offset(0)
        self._scroll_timer.start(450)

    def _start_scroll_animation(self):
        if not self._full_text:
            return

        overflow = self._text_width - self.width()
        if overflow <= 0:
            self._set_scroll_offset(0)
            return

        self.stop_scroll()
        self._scroll_range = overflow + self._edge_buffer_px
        duration = max(2200, int(self._scroll_range * 24))

        self._scroll_anim = QPropertyAnimation(self, b"scrollOffset", self)
        self._scroll_anim.setStartValue(0)
        self._scroll_anim.setEndValue(-self._scroll_range)
        self._scroll_anim.setDuration(duration)
        self._scroll_anim.setEasingCurve(QEasingCurve.Linear)
        self._scroll_anim.finished.connect(self._schedule_reverse)
        self._scroll_anim.start()

    def _reverse_scroll(self):
        if self._scroll_range <= 0:
            self._set_scroll_offset(0)
            return

        self._reverse_anim = QPropertyAnimation(self, b"scrollOffset", self)
        self._reverse_anim.setStartValue(self._scroll_offset)
        self._reverse_anim.setEndValue(0)
        self._reverse_anim.setDuration(max(2200, int(self._scroll_range * 24)))
        self._reverse_anim.setEasingCurve(QEasingCurve.Linear)
        self._reverse_anim.finished.connect(self._schedule_forward)
        self._reverse_anim.start()

    def _schedule_reverse(self):
        self._resume_reverse = True
        self._edge_pause_timer.start(self._edge_pause_ms)

    def _schedule_forward(self):
        self._resume_reverse = False
        self._edge_pause_timer.start(self._edge_pause_ms)

    def _on_edge_pause_timeout(self):
        if self._resume_reverse:
            self._reverse_scroll()
        else:
            self._start_scroll_animation()

    def stop_scroll(self):
        self._scroll_timer.stop()
        self._edge_pause_timer.stop()
        if self._scroll_anim is not None:
            self._scroll_anim.stop()
            self._scroll_anim = None
        if self._reverse_anim is not None:
            self._reverse_anim.stop()
            self._reverse_anim = None

    def _get_scroll_offset(self):
        return self._scroll_offset

    def _set_scroll_offset(self, value):
        self._scroll_offset = int(value)
        self.update()

    scrollOffset = Property(int, _get_scroll_offset, _set_scroll_offset)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._full_text:
            return

        painter = QPainter(self)
        painter.setPen(self._text_color)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        metrics = self.fontMetrics()
        baseline = (self.height() + metrics.ascent() - metrics.descent()) // 2
        painter.drawText(self._scroll_offset, baseline, self._full_text)


class AnimatedStatusToast(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._visible_pos = QPoint()
        self._hidden_pos = QPoint()
        self._hide_duration_ms = 10000

        self.setObjectName("statusToast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()
        self.setMaximumWidth(180)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(0)

        self.message_label = ScrollingLabel()
        self.message_label.set_max_content_width(164)
        layout.addWidget(self.message_label)

        self.show_slide_anim = QPropertyAnimation(self, b"pos", self)
        self.show_slide_anim.setDuration(260)
        self.show_slide_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.hide_slide_anim = QPropertyAnimation(self, b"pos", self)
        self.hide_slide_anim.setDuration(200)
        self.hide_slide_anim.setEasingCurve(QEasingCurve.InCubic)
        self.hide_slide_anim.finished.connect(self._finish_hide)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.dismiss)

    def set_hide_duration(self, duration_ms: int):
        self._hide_duration_ms = max(500, int(duration_ms))

    def show_message(self, message: str, level: str = "success", duration_ms: Optional[int] = None):
        palette = {
            "success": ("#0f8a4a", "#ffffff"),
            "error": ("#b23c3c", "#ffffff"),
            "info": ("#1f5a9e", "#ffffff"),
        }
        background, foreground = palette.get(level, palette["info"])

        self.hide_timer.stop()
        self.show_slide_anim.stop()
        self.hide_slide_anim.stop()
        self.message_label.stop_scroll()
        self.hide()

        self.message_label.setText(message)
        self.message_label.set_text_color(foreground)
        self.setStyleSheet(
            "QFrame#statusToast {"
            f"background-color: {background};"
            "border: none;"
            "border-radius: 6px;"
            "}"
            "QFrame#statusToastLabel {"
            "font-size: 10px;"
            "font-weight: 600;"
            "letter-spacing: 0.2px;"
            "}"
        )

        self.adjustSize()
        self._update_anchor_positions()
        self.move(self._hidden_pos)
        self.raise_()
        self.show()

        self.show_slide_anim.setStartValue(self._hidden_pos)
        self.show_slide_anim.setEndValue(self._visible_pos)
        self.show_slide_anim.start()

        self.hide_timer.start(duration_ms if duration_ms is not None else self._hide_duration_ms)

    def dismiss(self, animated: bool = True):
        if not self.isVisible():
            return

        self.hide_timer.stop()
        self.show_slide_anim.stop()
        self.message_label.stop_scroll()

        if not animated:
            self.hide()
            return

        self._update_anchor_positions()
        self.hide_slide_anim.setStartValue(self.pos())
        self.hide_slide_anim.setEndValue(self._hidden_pos)
        self.hide_slide_anim.start()

    def reposition(self):
        self._update_anchor_positions()
        if self.isVisible():
            self.move(self._visible_pos)

    def _update_anchor_positions(self):
        parent = self.parentWidget()
        if parent is None:
            return

        margin_left = 12
        margin_bottom = 12
        self.adjustSize()
        p_h = parent.height()

        visible_y = max(0, p_h - self.height() - margin_bottom)
        self._visible_pos = QPoint(margin_left, visible_y)
        self._hidden_pos = QPoint(margin_left, visible_y + 12)

    def _finish_hide(self):
        self.hide()
