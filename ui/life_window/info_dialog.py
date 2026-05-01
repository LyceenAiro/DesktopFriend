from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout

from ui.life_window.common import attach_window_shadow
from ui.styles.css import BOTTOM_BAR_STYLE, DIVIDER_STYLE, TOP_BAR_STYLE, WINDOW_SHELL_STYLE
from ui.styles.dialog_theme import apply_adobe_dialog_theme, apply_frameless_window_theme
from util.buff_icon_manager import BuffIconManager
from util.i18n import tr


class LifeInfoDialog(QDialog):
    def __init__(self, entry_name: str, desc: str, debug_lines: list[str] | None = None, icon_base64: str | None = None, link_handler: Callable[[str], None] | None = None, parent=None):
        super().__init__(parent)
        self._dragging = False
        self._drag_start = None
        self._link_handler = link_handler

        self.setWindowTitle(entry_name)
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(500, 300)
        self.setWindowFlags((self.windowFlags() & ~Qt.Tool) | Qt.Window | Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        shell = QFrame(self)
        shell.setObjectName("windowShell")
        shell.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(shell)
        attach_window_shadow(shell, self)

        root = QVBoxLayout(shell)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        self.top_bar = QFrame(shell)
        self.top_bar.setFixedHeight(56)
        self.top_bar.setStyleSheet(TOP_BAR_STYLE)
        top_row = QHBoxLayout(self.top_bar)
        top_row.setContentsMargins(20, 10, 14, 10)
        top_row.setSpacing(8)

        if icon_base64:
            icon_pixmap = BuffIconManager.base64_to_pixmap(icon_base64, 40)
            if icon_pixmap:
                icon_label = QLabel()
                icon_label.setPixmap(icon_pixmap)
                icon_label.setFixedSize(40, 40)
                icon_label.setStyleSheet("background: transparent; border: none;")
                top_row.addWidget(icon_label)

        self.title_label = QLabel(entry_name)
        self.title_label.setObjectName("title")
        self.title_label.setStyleSheet("font-size: 18px;")
        top_row.addWidget(self.title_label)
        top_row.addStretch()

        root.addWidget(self.top_bar)

        divider = QFrame(shell)
        divider.setFixedHeight(1)
        divider.setStyleSheet(DIVIDER_STYLE)
        root.addWidget(divider)

        content_frame = QFrame(shell)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(18, 14, 18, 14)
        content_layout.setSpacing(10)

        desc_label = QLabel(desc if desc else tr("life.common.no_desc"))
        desc_label.setWordWrap(True)
        if self._link_handler is not None:
            desc_label.setTextInteractionFlags(Qt.LinksAccessibleByMouse | Qt.TextSelectableByMouse)
            desc_label.setOpenExternalLinks(False)
            desc_label.linkActivated.connect(self._on_link_activated)
        else:
            desc_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        desc_label.setStyleSheet("font-size: 13px; line-height: 1.5; color: #d6d6d6; background: transparent; border: none;")
        content_layout.addWidget(desc_label)
        content_layout.addStretch()

        if debug_lines:
            debug_hint = QLabel(tr("life.info.debug"))
            debug_hint.setObjectName("helperText")
            content_layout.addWidget(debug_hint)

            self.content_edit = QTextEdit()
            self.content_edit.setReadOnly(True)
            self.content_edit.setMinimumHeight(96)
            self.content_edit.setPlainText("\n".join(debug_lines))
            content_layout.addWidget(self.content_edit)
        root.addWidget(content_frame, 1)

        bottom = QFrame(shell)
        bottom.setObjectName("bottomBar")
        bottom.setFixedHeight(50)
        bottom.setStyleSheet(BOTTOM_BAR_STYLE)
        bottom_row = QHBoxLayout(bottom)
        bottom_row.setContentsMargins(16, 8, 16, 8)
        bottom_row.addStretch()

        ok_btn = QPushButton(tr("common.close"))
        ok_btn.clicked.connect(self.accept)
        bottom_row.addWidget(ok_btn)
        root.addWidget(bottom)

        apply_adobe_dialog_theme(self)
        apply_frameless_window_theme(self)
        self.setStyleSheet(self.styleSheet() + WINDOW_SHELL_STYLE)

        self.top_bar.installEventFilter(self)
        self.title_label.installEventFilter(self)

    def _on_link_activated(self, href: str) -> None:
        if self._link_handler is not None:
            self._link_handler(href)

    def event(self, event):
        if event.type() == QEvent.WindowDeactivate and self.isVisible():
            self.reject()
            return True
        return super().event(event)

    def eventFilter(self, watched, event):
        if watched in (self.top_bar, self.title_label):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._dragging = True
                self._drag_start = event.globalPosition().toPoint()
                return True
            if event.type() == QEvent.MouseMove and self._dragging and self._drag_start is not None:
                current_global = event.globalPosition().toPoint()
                delta = current_global - self._drag_start
                self.move(self.pos() + delta)
                self._drag_start = current_global
                return True
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._dragging = False
                self._drag_start = None
                return True
        return super().eventFilter(watched, event)
