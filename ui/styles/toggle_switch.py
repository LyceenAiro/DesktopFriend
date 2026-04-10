from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox


class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setText("")
        self.setFixedSize(38, 22)
        self._is_hovered = False
        self._handle_position = 1.0 if self.isChecked() else 0.0
        self._animation = QPropertyAnimation(self, b"handle_position", self)
        self._animation.setDuration(120)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate_handle)

    def sizeHint(self):
        return QSize(38, 22)

    def minimumSizeHint(self):
        return QSize(38, 22)

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

        w = self.width()
        h = self.height()
        radius = h / 2
        margin = 2
        knob_d = h - margin * 2

        if self.isChecked():
            track_color = QColor("#0F6CBD")
            border_color = QColor("#0A5CA8")
            if self._is_hovered:
                track_color = QColor("#115EA3")
                border_color = QColor("#0B4F8A")
        else:
            track_color = QColor("#F3F3F3")
            border_color = QColor("#8A8886")
            if self._is_hovered:
                track_color = QColor("#EDEBE9")
                border_color = QColor("#605E5C")

        if not self.isEnabled():
            track_color = QColor("#F3F2F1")
            border_color = QColor("#D2D0CE")
            track_color.setAlpha(210)
            border_color.setAlpha(210)

        painter.setPen(QPen(border_color, 1))
        painter.setBrush(track_color)
        painter.drawRoundedRect(0.5, 0.5, w - 1, h - 1, radius, radius)

        travel = w - knob_d - margin * 2
        knob_x = margin + travel * self._handle_position
        knob_color = QColor("#FFFFFF")
        knob_border = QColor("#D1D1D1")
        if not self.isEnabled():
            knob_color = QColor("#FAF9F8")
            knob_border = QColor("#E1DFDD")

        painter.setPen(QPen(knob_border, 1))
        painter.setBrush(knob_color)
        painter.drawEllipse(knob_x, margin, knob_d, knob_d)
