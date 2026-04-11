from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QFrame,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from ui.styles.dialog_theme import apply_adobe_dialog_theme, apply_frameless_window_theme
from util.i18n import tr


class ConfirmDialog(QDialog):
    """统一美术风格的确认对话框"""
    
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowFlags((self.windowFlags() & ~Qt.Tool) | Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(420, 200)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(0)

        shell = QFrame(self)
        shell.setObjectName("windowShell")
        shell.setAttribute(Qt.WA_StyledBackground, True)
        outer_layout.addWidget(shell)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(54)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 80))
        shell.setGraphicsEffect(shadow)
        shell.setStyleSheet(
            "QFrame#windowShell { background-color: #262626; border: 1px solid #3a3a3a; border-radius: 14px; }"
        )

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(24, 20, 24, 20)
        shell_layout.setSpacing(0)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("title")
        self.title_label.setStyleSheet("color: #f5f5f5; font-size: 18px; font-weight: 650;")
        shell_layout.addWidget(self.title_label)

        shell_layout.addSpacing(12)

        self.message_label = QLabel(message)
        self.message_label.setStyleSheet("color: #d6d6d6; font-size: 13px; line-height: 1.6;")
        self.message_label.setWordWrap(True)
        shell_layout.addWidget(self.message_label)

        shell_layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch()

        self.cancel_button = QPushButton(tr("common.cancel"))
        self.cancel_button.setMinimumWidth(80)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                min-height: 34px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                color: #d7d7d7;
                background-color: #353535;
                border: 1px solid #4a4a4a;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.confirm_button = QPushButton(tr("common.confirm"))
        self.confirm_button.setMinimumWidth(80)
        self.confirm_button.setObjectName("primaryButton")
        self.confirm_button.setStyleSheet("""
            QPushButton#primaryButton {
                min-height: 34px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                color: white;
                background-color: #e6453a;
                border: 1px solid #ff776d;
            }
            QPushButton#primaryButton:hover {
                background-color: #f6574b;
            }
        """)
        self.confirm_button.clicked.connect(self.accept)
        button_layout.addWidget(self.confirm_button)

        shell_layout.addLayout(button_layout)

        apply_adobe_dialog_theme(self)
        apply_frameless_window_theme(self)
