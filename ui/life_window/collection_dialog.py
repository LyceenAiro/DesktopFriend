from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ui.life_window.common import attach_window_shadow
from ui.life_window.info_dialog import LifeInfoDialog
from ui.styles.css import BOTTOM_BAR_STYLE, DIVIDER_STYLE, TOP_BAR_STYLE, WINDOW_SHELL_STYLE
from ui.styles.dialog_theme import apply_adobe_dialog_theme, apply_frameless_window_theme
from util.i18n import tr


class CollectionDetailDialog(QDialog):
    """图鉴详情弹窗：展示某一类别下所有条目的收集状态。"""

    def __init__(
        self,
        category_name: str,
        entries: list[dict],
        get_detail: Callable[[str], dict | None] | None = None,
        developer_mode: bool = False,
        get_outcome_detail: Callable[[str], dict | None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._dragging = False
        self._drag_start = None
        self._resizing = False
        self._resize_start_y = 0
        self._resize_start_height = 0
        self._get_detail = get_detail
        self._get_outcome_detail = get_outcome_detail
        self._developer_mode = developer_mode

        self.setWindowTitle(category_name)
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(660, 480)
        self.setFixedWidth(660)
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

        # Top bar
        self.top_bar = QFrame(shell)
        self.top_bar.setFixedHeight(48)
        self.top_bar.setStyleSheet(TOP_BAR_STYLE)
        top_row = QHBoxLayout(self.top_bar)
        top_row.setContentsMargins(20, 10, 14, 10)
        top_row.setSpacing(8)

        self.title_label = QLabel(category_name)
        self.title_label.setObjectName("title")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        top_row.addWidget(self.title_label)

        total = len(entries)
        unlocked = sum(1 for e in entries if e.get("unlocked"))
        count_label = QLabel(f"{unlocked}/{total}")
        count_label.setStyleSheet("font-size: 13px; color: #8e8e8e; background: transparent; border: none;")
        top_row.addWidget(count_label)

        top_row.addStretch()

        root.addWidget(self.top_bar)

        divider = QFrame(shell)
        divider.setFixedHeight(1)
        divider.setStyleSheet(DIVIDER_STYLE)
        root.addWidget(divider)

        # 条目列表（2 列网格，可滚动）
        scroll = QScrollArea(shell)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        scroll_content.setObjectName("collectionScrollContent")
        scroll_content.setStyleSheet("QWidget#collectionScrollContent { background: transparent; }")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        scroll_layout.setSpacing(4)

        COLS = 2
        for i in range(0, len(entries), COLS):
            row_frame = QFrame()
            row_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            for j in range(COLS):
                if i + j < len(entries):
                    box = self._build_entry_box(entries[i + j])
                    row_layout.addWidget(box, 1)
                else:
                    spacer = QFrame()
                    spacer.setStyleSheet("QFrame { background: transparent; border: none; }")
                    row_layout.addWidget(spacer, 1)

            scroll_layout.addWidget(row_frame)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        # Bottom bar
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

        # 底部高度调节手柄
        self._resize_handle = QFrame(shell)
        self._resize_handle.setFixedHeight(8)
        self._resize_handle.setCursor(Qt.SizeVerCursor)
        self._resize_handle.setStyleSheet("QFrame { background: transparent; }")
        self._resize_handle.installEventFilter(self)
        root.addWidget(self._resize_handle)

        apply_adobe_dialog_theme(self)
        apply_frameless_window_theme(self)
        self.setStyleSheet(self.styleSheet() + WINDOW_SHELL_STYLE)

        self.top_bar.installEventFilter(self)
        self.title_label.installEventFilter(self)

    def _build_entry_box(self, entry: dict) -> QFrame:
        unlocked = entry.get("unlocked", False)
        entry_id = str(entry.get("id", ""))
        show_info = unlocked or self._developer_mode
        name = str(entry.get("name", entry_id)) if show_info else "???"
        desc = str(entry.get("desc", "")) if show_info else ""

        box = QFrame()
        box.setObjectName("collectionEntryBox")
        if unlocked:
            box.setStyleSheet("""
                QFrame#collectionEntryBox {
                    background: #2a2a2a; border-radius: 8px;
                    border: 1px solid #3a3a3a;
                }
            """)
        else:
            box.setStyleSheet("""
                QFrame#collectionEntryBox {
                    background: #1e1e1e; border-radius: 8px;
                    border: 1px solid #2a2a2a;
                }
            """)

        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        # 名称行
        name_row = QHBoxLayout()
        name_row.setSpacing(6)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {'#e0e0e0' if unlocked else '#555555'}; "
            "background: transparent; border: none;"
        )
        name_row.addWidget(name_lbl, 1)

        # 状态标签
        if unlocked:
            badge = QLabel(tr("life.collection.unlocked_badge"))
            badge.setStyleSheet("""
                QLabel {
                    font-size: 10px; font-weight: 600; color: #4caf50;
                    background: #1a3a1a; border: 1px solid #2a5a2a;
                    border-radius: 3px; padding: 0px 6px;
                }
            """)
        else:
            badge = QLabel(tr("life.collection.locked_badge"))
            badge.setStyleSheet("""
                QLabel {
                    font-size: 10px; font-weight: 600; color: #555555;
                    background: #1a1a1a; border: 1px solid #2a2a2a;
                    border-radius: 3px; padding: 0px 6px;
                }
            """)
        name_row.addWidget(badge)

        layout.addLayout(name_row)

        # 描述（仅已解锁时展示）
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(
                "font-size: 11px; color: #9e9e9e; background: transparent; border: none;"
            )
            layout.addWidget(desc_lbl)

        # 查看信息按钮（已解锁或开发者模式下展示）
        if show_info and self._get_detail is not None:
            info_btn = QPushButton(tr("life.collection.view_info"))
            info_btn.setObjectName("collectionInfoBtn")
            info_btn.setFixedHeight(26)
            info_btn.setStyleSheet("""
                QPushButton#collectionInfoBtn {
                    font-size: 11px; padding: 0 10px;
                    background: #3a3a3a; color: #dcdcdc;
                    border: none; border-radius: 4px;
                }
                QPushButton#collectionInfoBtn:hover { background: #4a4a4a; color: #fff; }
                QPushButton#collectionInfoBtn:pressed { background: #2a2a2a; }
            """)
            info_btn.clicked.connect(lambda checked, eid=entry_id: self._open_info(eid))
            layout.addWidget(info_btn, 0, Qt.AlignRight)

        return box

    def _open_info(self, entry_id: str):
        if self._get_detail is None:
            return
        detail = self._get_detail(entry_id)
        if not detail:
            return
        name = str(detail.get("name", entry_id))
        desc = str(detail.get("desc", "")).strip()
        is_rich = bool(detail.get("_is_rich_desc"))
        outcome_ids: list[str] = detail.get("_outcome_ids", []) or []

        link_handler = None
        if is_rich and outcome_ids and self._get_outcome_detail is not None:
            def _handle_link(href: str) -> None:
                if href.startswith("outcome:"):
                    oid = href[len("outcome:"):]
                    od = self._get_outcome_detail(oid)
                    if od:
                        oname = str(od.get("name", oid))
                        odesc = str(od.get("desc", "")).strip()
                        LifeInfoDialog(
                            oname, odesc,
                            icon_base64=od.get("icon_base64"),
                            parent=self,
                        ).show()
            link_handler = _handle_link

        dialog = LifeInfoDialog(
            name, desc,
            icon_base64=detail.get("icon_base64"),
            link_handler=link_handler,
            parent=self,
        )
        dialog.show()

    def event(self, event):
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
        if watched is self._resize_handle:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._resizing = True
                self._resize_start_y = event.globalPosition().toPoint().y()
                self._resize_start_height = self.height()
                event.accept()
                return True
            if event.type() == QEvent.MouseMove and self._resizing:
                current_y = event.globalPosition().toPoint().y()
                delta_y = current_y - self._resize_start_y
                new_height = max(300, self._resize_start_height + delta_y)
                self.resize(self.width(), new_height)
                event.accept()
                return True
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._resizing = False
                event.accept()
                return True
        return super().eventFilter(watched, event)
