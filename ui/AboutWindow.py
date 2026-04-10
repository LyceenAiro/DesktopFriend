from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from util.version import version
from ui.styles.dialog_theme import apply_adobe_dialog_theme, apply_frameless_window_theme

class AboutWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.setModal(True)
        self.setFixedSize(500, 330)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(0)

        self.window_shell = QFrame(self)
        self.window_shell.setObjectName("windowShell")
        self.window_shell.setAttribute(Qt.WA_StyledBackground, True)
        outer_layout.addWidget(self.window_shell)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(56)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 72))
        self.window_shell.setGraphicsEffect(shadow)
        self.window_shell.setStyleSheet(
            "QFrame#windowShell { background-color: #262626; border: 1px solid #3a3a3a; border-radius: 14px; }"
        )

        layout = QVBoxLayout(self.window_shell)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title_label = QLabel("DesktopFriend")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("title")
        layout.addWidget(title_label)

        version_label = QLabel(f"v{version}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setObjectName("subtitle")
        layout.addWidget(version_label)

        author_label = QLabel("LyceenAiro@2026")
        author_label.setAlignment(Qt.AlignCenter)
        author_label.setObjectName("fieldLabel")
        layout.addWidget(author_label)

        link_label = QLabel("github.com/LyceenAiro/DesktopFriend")
        link_label.setAlignment(Qt.AlignCenter)
        link_label.setObjectName("helperText")
        layout.addWidget(link_label)

        layout.addStretch()

        button_row = QHBoxLayout()
        button_row.addStretch()

        close_button = QPushButton("关闭")
        close_button.setObjectName("primaryButton")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        apply_adobe_dialog_theme(self)
        apply_frameless_window_theme(self)