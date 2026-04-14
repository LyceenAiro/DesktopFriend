from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QGraphicsDropShadowEffect, QPushButton


def style_window_controls(min_button: QPushButton, close_button: QPushButton, pin_button: QPushButton | None = None) -> None:
    min_button.setStyleSheet(
        """
        QPushButton#minButton {
            background-color: transparent;
            border: 1px solid transparent;
            color: #dcdcdc;
            font-size: 16px;
            font-weight: 700;
            border-radius: 8px;
            padding: 0px;
        }
        QPushButton#minButton:hover {
            background-color: #3a3a3a;
            color: #ffffff;
        }
        QPushButton#minButton:pressed {
            background-color: #2e2e2e;
            color: #ffffff;
        }
        """
    )

    close_button.setStyleSheet(
        """
        QPushButton#closeButton {
            background-color: transparent;
            border: 1px solid transparent;
            color: #dcdcdc;
            font-size: 18px;
            font-weight: 600;
            border-radius: 8px;
            padding: 0px;
        }
        QPushButton#closeButton:hover {
            background-color: #f95f53;
            color: #ffffff;
        }
        QPushButton#closeButton:pressed {
            background-color: #d94a3f;
            color: #ffffff;
        }
        """
    )

    if pin_button is not None:
        pin_button.setStyleSheet(
            """
            QPushButton#pinButton {
                background-color: transparent;
                border: 1px solid transparent;
                color: #dcdcdc;
                font-size: 15px;
                font-weight: 700;
                border-radius: 8px;
                padding: 0px;
            }
            QPushButton#pinButton:hover {
                background-color: #3a3a3a;
                color: #ffffff;
            }
            QPushButton#pinButton:checked {
                background-color: #1f5a9e;
                border: 1px solid #3f79c3;
                color: #ffffff;
            }
            """
        )


def attach_window_shadow(target: QFrame, owner: QDialog) -> None:
    shadow = QGraphicsDropShadowEffect(owner)
    shadow.setBlurRadius(20)
    shadow.setOffset(0, 2)
    shadow.setColor(QColor(0, 0, 0, 48))
    target.setGraphicsEffect(shadow)


def create_pin_icon(color: str, active: bool = False) -> QIcon:
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    head_path = QPainterPath()
    head_path.moveTo(QPointF(5.5, 4.5))
    head_path.lineTo(QPointF(12.5, 4.5))
    head_path.lineTo(QPointF(10.3, 8.2))
    head_path.lineTo(QPointF(7.7, 8.2))
    head_path.closeSubpath()

    if active:
        painter.fillPath(head_path, QColor(color))
    else:
        painter.drawPath(head_path)

    painter.drawLine(QPointF(9.0, 8.2), QPointF(9.0, 15.6))

    painter.end()
    return QIcon(pixmap)
