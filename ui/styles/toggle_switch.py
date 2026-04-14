from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox


class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setText("")
        self.setFixedSize(42, 24)
        self._is_hovered = False
        self._handle_position = 1.0 if self.isChecked() else 0.0
        self._animation = QPropertyAnimation(self, b"handle_position", self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate_handle)

    def sizeHint(self):
        return QSize(42, 24)

    def minimumSizeHint(self):
        return QSize(42, 24)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def enterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def _get_handle_position(self):
        return self._handle_position

    def _set_handle_position(self, value):
        self._handle_position = float(value)
        self.update()

    handle_position = Property(float, _get_handle_position, _set_handle_position)

    def _animate_handle(self, checked):
        self._animation.stop()
        self._animation.setStartValue(self._handle_position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        radius = h / 2
        outer_margin = 1.5
        knob_margin = 3.5
        knob_d = h - knob_margin * 2

        if self.isChecked():
            # 开启态对齐当前窗口主色（红色强调）
            track_color = QColor("#E6453A")
            border_color = QColor("#FF776D")
            inner_color = QColor("#F06A60")
            if self._is_hovered:
                track_color = QColor("#F6574B")
                border_color = QColor("#FF8A81")
                inner_color = QColor("#FF7A70")
        else:
            # 关闭态对齐深色面板层级
            track_color = QColor("#242424")
            border_color = QColor("#4A4A4A")
            inner_color = QColor("#2D2D2D")
            if self._is_hovered:
                track_color = QColor("#2F2F2F")
                border_color = QColor("#666666")
                inner_color = QColor("#393939")

        if not self.isEnabled():
            track_color = QColor("#2B2B2B")
            border_color = QColor("#404040")
            inner_color = QColor("#323232")
            track_color.setAlpha(210)
            border_color.setAlpha(210)
            inner_color.setAlpha(210)

        track_rect = QRectF(outer_margin, outer_margin, w - outer_margin * 2, h - outer_margin * 2)
        painter.setPen(QPen(border_color, 1.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, radius, radius)

        inner_rect = QRectF(
            track_rect.x() + 1,
            track_rect.y() + 1,
            track_rect.width() - 2,
            track_rect.height() - 2,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(inner_color)
        painter.drawRoundedRect(inner_rect, radius - 1, radius - 1)

        travel = w - knob_d - knob_margin * 2
        knob_x = knob_margin + travel * self._handle_position
        knob_y = (h - knob_d) / 2
        knob_color = QColor("#F7F7F7")
        knob_border = QColor("#C8C8C8")
        shadow_color = QColor(0, 0, 0, 55)
        if not self.isEnabled():
            knob_color = QColor("#BEBEBE")
            knob_border = QColor("#8C8C8C")
            shadow_color = QColor(0, 0, 0, 25)

        knob_rect = QRectF(knob_x, knob_y, knob_d, knob_d)
        shadow_rect = QRectF(knob_rect.x(), knob_rect.y() + 0.8, knob_rect.width(), knob_rect.height())
        painter.setPen(Qt.NoPen)
        painter.setBrush(shadow_color)
        painter.drawEllipse(shadow_rect)

        painter.setPen(QPen(knob_border, 1.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(knob_color)
        painter.drawEllipse(knob_rect)

        highlight_rect = QRectF(knob_rect.x() + 2.2, knob_rect.y() + 2.0, knob_rect.width() - 4.4, knob_rect.height() * 0.38)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 42 if self.isEnabled() else 20))
        painter.drawEllipse(highlight_rect)
