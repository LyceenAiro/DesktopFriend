from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QFrame,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor
import traceback
import sys
from ui.styles.dialog_theme import apply_adobe_dialog_theme, apply_frameless_window_theme
from util.i18n import tr

class ErrorDialog(QDialog):
    def __init__(self, exc_type, exc_value, exc_traceback, parent=None):
        super().__init__(parent)
        self._dragging = False
        self._drag_start_pos = None
        self.setWindowTitle(tr("error.title"))
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowFlags((self.windowFlags() & ~Qt.Tool) | Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(600, 600)

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
        shell_layout.setContentsMargins(1, 1, 1, 1)
        shell_layout.setSpacing(0)

        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(58)
        top_bar_layout = QHBoxLayout(self.top_bar)
        top_bar_layout.setContentsMargins(22, 12, 16, 10)
        top_bar_layout.setSpacing(0)

        self.title_label = QLabel(tr("error.title"))
        self.title_label.setObjectName("title")
        top_bar_layout.addWidget(self.title_label, 0, Qt.AlignVCenter)
        top_bar_layout.addStretch()

        close_button = QPushButton("✕")
        close_button.setObjectName("closeButton")
        close_button.setFixedSize(40, 30)
        close_button.clicked.connect(self.reject)
        close_button.setStyleSheet(
            """
            QPushButton#closeButton {
                background-color: transparent;
                border: 1px solid transparent;
                color: #dcdcdc;
                font-size: 16px;
                font-weight: 600;
                border-radius: 8px;
            }
            QPushButton#closeButton:hover {
                background-color: #f95f53;
                color: #ffffff;
            }
            QPushButton#closeButton:pressed {
                background-color: #d94a3f;
            }
            """
        )
        top_bar_layout.addWidget(close_button, 0, Qt.AlignVCenter)

        shell_layout.addWidget(self.top_bar)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("QFrame { background-color: #3a3a3a; border: none; }")
        shell_layout.addWidget(divider)

        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(22, 18, 22, 16)
        content_layout.setSpacing(14)

        subtitle_label = QLabel(tr("error.subtitle"))
        subtitle_label.setObjectName("subtitle")
        content_layout.addWidget(subtitle_label)

        error_text = f"{exc_type.__name__}: {exc_value}"
        error_label = QLabel(error_text)
        error_label.setObjectName("fieldLabel")
        error_label.setWordWrap(True)
        content_layout.addWidget(error_label)

        stack_label = QLabel(tr("error.stack"))
        stack_label.setObjectName("sectionTitle")
        content_layout.addWidget(stack_label)

        stack_text = QTextEdit()
        stack_text.setPlainText("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        stack_text.setReadOnly(True)
        content_layout.addWidget(stack_text, 1)

        shell_layout.addWidget(content, 1)

        bottom_bar = QFrame()
        bottom_bar.setObjectName("bottomBar")
        bottom_bar.setFixedHeight(60)
        bottom_bar.setStyleSheet(
            "QFrame#bottomBar { background-color: #1f1f1f; border-top: 1px solid #3a3a3a; "
            "border-bottom-left-radius: 13px; border-bottom-right-radius: 13px; }"
        )
        button_layout = QHBoxLayout(bottom_bar)
        button_layout.setContentsMargins(22, 12, 22, 12)
        button_layout.setSpacing(10)
        button_layout.addStretch()

        ok_button = QPushButton(tr("common.ok"))
        ok_button.setObjectName("primaryButton")
        ok_button.setMinimumWidth(90)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        quit_button = QPushButton(tr("error.quit_app"))
        quit_button.setMinimumWidth(100)
        quit_button.clicked.connect(self.quit_app)
        button_layout.addWidget(quit_button)

        shell_layout.addWidget(bottom_bar)

        apply_adobe_dialog_theme(self)
        apply_frameless_window_theme(self)

        stack_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #1f1f1f;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                color: #d6d6d6;
                padding: 8px;
                font-size: 12px;
            }
            """
        )

        self._drag_widgets = [self, shell, self.top_bar, self.title_label]
        for widget in self._drag_widgets:
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched in getattr(self, "_drag_widgets", []):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if watched in (self.top_bar, self.title_label):
                    self._dragging = True
                    self._drag_start_pos = event.globalPosition().toPoint()
                    return True

            if event.type() == QEvent.MouseMove and self._dragging:
                current_global = event.globalPosition().toPoint()
                delta = current_global - self._drag_start_pos
                self.move(self.pos() + delta)
                self._drag_start_pos = current_global
                return True

            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._dragging = False
                self._drag_start_pos = None

        return super().eventFilter(watched, event)

    def quit_app(self):
        sys.exit(1)