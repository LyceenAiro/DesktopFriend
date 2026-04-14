"""可分页的子标签栏组件，用于 Life 窗口各标签页的分类筛选。

特性：
- 左对齐
- 底部分割线
- 翻页箭头始终可见，不可用时灰显
- 每页固定 per_page 个槽位，不足时用占位符填充
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget


_ACTIVE_STYLE = (
    "QPushButton { background-color: #0078d4; color: #ffffff; border: none; "
    "border-radius: 6px; padding: 2px 12px; font-weight: 600; }"
    "QPushButton:hover { background-color: #1a86d9; }"
)
_INACTIVE_STYLE = (
    "QPushButton { background-color: #2d2d2d; color: #cccccc; "
    "border: 1px solid #3a3a3a; border-radius: 6px; padding: 2px 12px; }"
    "QPushButton:hover { background-color: #383838; }"
)
_NAV_STYLE = (
    "QPushButton { background-color: transparent; color: #cccccc; "
    "border: none; border-radius: 4px; padding: 0px; font-weight: 700; font-size: 14px; "
    "min-width: 24px; max-width: 24px; }"
)
_NAV_DISABLED_STYLE = (
    "QPushButton { background-color: transparent; color: #555555; "
    "border: none; border-radius: 4px; padding: 0px; font-weight: 700; font-size: 14px; "
    "min-width: 24px; max-width: 24px; }"
)
_SEPARATOR_STYLE = "background-color: #3a3a3a;"


class PaginatedSubTabBar(QFrame):
    """可分页子标签栏。

    Parameters
    ----------
    on_switch : Callable[[str | None], None]
        切换分类回调，参数为 cls_id（None = 全部）。
    parent : QWidget | None
    per_page : int
        每页显示的按钮数量（默认 4）。
    """

    def __init__(self, on_switch: Callable[[str | None], None], parent: QWidget | None = None, per_page: int = 4):
        super().__init__(parent)
        self._on_switch = on_switch
        self._buttons: list[tuple[str | None, QPushButton]] = []  # (cls_id, btn)
        self._active_class: str | None = None
        self._page_index: int = 0
        self._per_page_count: int = max(1, per_page)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 导航栏：左箭头 | 按钮槽位区(固定宽度) | 右箭头
        self._nav_frame = QFrame()
        nav_layout = QHBoxLayout(self._nav_frame)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)

        self._prev_btn = QPushButton("‹")
        self._prev_btn.setFixedSize(24, 28)
        self._prev_btn.setStyleSheet(_NAV_DISABLED_STYLE)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.clicked.connect(self._page_prev)
        nav_layout.addWidget(self._prev_btn, 0)

        # 按钮容器 — 内部始终放 per_page 个等宽槽位
        self._btn_frame = QFrame()
        self._btn_layout = QHBoxLayout(self._btn_frame)
        self._btn_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_layout.setSpacing(6)
        nav_layout.addWidget(self._btn_frame, 1)

        self._next_btn = QPushButton("›")
        self._next_btn.setFixedSize(24, 28)
        self._next_btn.setStyleSheet(_NAV_DISABLED_STYLE)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self._page_next)
        nav_layout.addWidget(self._next_btn, 0)

        root_layout.addWidget(self._nav_frame)

        # 分割线
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(_SEPARATOR_STYLE)
        root_layout.addWidget(separator)

        # 底部间隔
        root_layout.addSpacing(8)

    # ── public API ──────────────────────────────────

    def set_buttons(self, items: list[tuple[str | None, str]]) -> None:
        """重建按钮列表。

        Parameters
        ----------
        items : list of (cls_id, label)
            cls_id = None 表示"全部"。
        """
        self._clear_buttons()
        for cls_id, label in items:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(self._make_switch_cb(cls_id))
            self._buttons.append((cls_id, btn))
        self._page_index = 0
        self._relayout()

    def set_active(self, cls_id: str | None) -> None:
        self._active_class = cls_id
        self._update_styles()

    def get_active(self) -> str | None:
        return self._active_class

    def has_buttons(self) -> bool:
        return len(self._buttons) > 0

    # ── internals ───────────────────────────────────

    def _clear_buttons(self) -> None:
        for _, btn in self._buttons:
            btn.setParent(None)
            btn.deleteLater()
        self._buttons.clear()

    def _make_switch_cb(self, cls_id: str | None):
        def _cb():
            self._active_class = cls_id
            self._update_styles()
            self._on_switch(cls_id)
        return _cb

    def _relayout(self) -> None:
        """重新布局当前页按钮，不足 per_page 个时用占位符填充。"""
        # 清空按钮容器
        while self._btn_layout.count():
            item = self._btn_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        if not self._buttons:
            self._nav_frame.setVisible(False)
            return

        self._nav_frame.setVisible(True)

        per = self._per_page_count
        page_buttons = self._get_page_buttons()

        # 放置当前页的按钮
        for _, btn in page_buttons:
            self._btn_layout.addWidget(btn, 1)

        # 不足 per_page 个时用不可见占位符填充，让按钮宽度均匀
        for _ in range(per - len(page_buttons)):
            spacer = QFrame()
            spacer.setFixedHeight(28)
            spacer.setStyleSheet("background: transparent; border: none;")
            self._btn_layout.addWidget(spacer, 1)

        # 更新翻页按钮状态
        total_pages = self._total_pages()
        can_prev = self._page_index > 0
        can_next = self._page_index < total_pages - 1
        self._prev_btn.setEnabled(can_prev)
        self._next_btn.setEnabled(can_next)
        self._prev_btn.setStyleSheet(_NAV_STYLE if can_prev else _NAV_DISABLED_STYLE)
        self._next_btn.setStyleSheet(_NAV_STYLE if can_next else _NAV_DISABLED_STYLE)

        self._update_styles()

    def _per_page(self) -> int:
        return self._per_page_count

    def _total_pages(self) -> int:
        per = self._per_page_count
        total = len(self._buttons)
        if total <= per:
            return 1
        return (total + per - 1) // per

    def _get_page_buttons(self) -> list[tuple[str | None, QPushButton]]:
        per = self._per_page_count
        total = len(self._buttons)
        if total <= per:
            return list(self._buttons)
        start = self._page_index * per
        end = min(start + per, total)
        return self._buttons[start:end]

    def _page_prev(self) -> None:
        if self._page_index > 0:
            self._page_index -= 1
            self._relayout()

    def _page_next(self) -> None:
        if self._page_index < self._total_pages() - 1:
            self._page_index += 1
            self._relayout()

    def _update_styles(self) -> None:
        for cls_id, btn in self._buttons:
            btn.setStyleSheet(_ACTIVE_STYLE if cls_id == self._active_class else _INACTIVE_STYLE)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # 分页数固定，resize 不需要重新布局；
        # 在此调用 _relayout 会导致无限递归（布局变化→resize→布局变化）。
