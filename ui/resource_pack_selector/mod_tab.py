"""Mod 管理标签页

显示已安装的 mod 列表，支持拖拽调整加载顺序（热加载、自动保存至 mod/load_order.json）。
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, Signal, QPoint
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from util.i18n import tr
from util.log import _log

_ORDER_FILE = Path("mod") / "load_order.json"


def _read_order() -> list[str]:
    try:
        if _ORDER_FILE.exists():
            data = json.loads(_ORDER_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                order = data.get("order", [])
                if isinstance(order, list):
                    return [str(x) for x in order]
    except Exception:
        pass
    return []


def _write_order(order: list[str]) -> None:
    try:
        _ORDER_FILE.parent.mkdir(parents=True, exist_ok=True)
        _ORDER_FILE.write_text(
            json.dumps({"order": order}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        _log.WARN(f"[ModTab]保存加载顺序失败: {e}")


class ModDetailDialog(QDialog):
    """Mod 详细信息弹窗。"""

    def __init__(
        self,
        mod_id: str,
        pack_info: dict,
        issues: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Dialog
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 外层容器（带圆角背景）
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        shell = QFrame()
        shell.setObjectName("detailShell")
        outer.addWidget(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(8)

        name = pack_info.get("name") or mod_id
        version = pack_info.get("version", "")
        author = pack_info.get("author", "")
        description = pack_info.get("description", "")
        requires = pack_info.get("requires", [])
        conflicts = pack_info.get("conflicts", [])

        title_lbl = QLabel(f"{name}" + (f"  v{version}" if version else ""))
        title_lbl.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #f0f0f0; margin-bottom: 4px;"
        )
        layout.addWidget(title_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("border: none; background: #2e2e2e; max-height: 1px;")
        layout.addWidget(sep)

        def _add_row(label: str, value: str) -> None:
            if not value:
                return
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label)
            lbl.setFixedWidth(68)
            lbl.setStyleSheet("color: #6a8faf; font-size: 12px;")
            val = QLabel(value)
            val.setStyleSheet("color: #d0d0d0; font-size: 12px;")
            val.setWordWrap(True)
            row.addWidget(lbl, 0, Qt.AlignTop)
            row.addWidget(val, 1)
            layout.addLayout(row)

        _add_row(tr("mod_manager.detail.id"), mod_id)
        _add_row(tr("mod_manager.detail.author"), author)
        _add_row(tr("mod_manager.detail.description"), description)
        if requires:
            _add_row(tr("mod_manager.detail.requires"), ", ".join(str(r) for r in requires))
        if conflicts:
            _add_row(tr("mod_manager.detail.conflicts"), ", ".join(str(c) for c in conflicts))

        if issues:
            issues_title = QLabel(tr("mod_manager.detail.issues"))
            issues_title.setStyleSheet(
                "color: #e07030; font-size: 12px; font-weight: 600; margin-top: 4px;"
            )
            layout.addWidget(issues_title)
            for issue in issues:
                il = QLabel(f"  • {issue}")
                il.setStyleSheet("color: #e09050; font-size: 12px;")
                il.setWordWrap(True)
                layout.addWidget(il)

        layout.addStretch()

        close_btn = QPushButton(tr("common.close"))
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

        self.setStyleSheet("""
            QFrame#detailShell {
                background-color: #1a1f28;
                border: 1px solid #2e3a4a;
                border-radius: 12px;
            }
            QLabel { background: transparent; }
        """)
        self._drag_pos: QPoint | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None


class ModListItem(QWidget):
    """单个 mod 条目（名称 / 版本 / 警告，详情由弹窗展示）。"""

    def __init__(
        self,
        mod_id: str,
        pack_info: dict,
        issues: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.mod_id = mod_id
        self._pack_info = pack_info
        self._issues = issues
        # 不在此处设置 stylesheet，避免打断父级样式表继承（会导致子 widget 样式失效）
        # 黄色背景通过 paintEvent 直接绘制

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        grip = QLabel("⠿")
        grip.setStyleSheet("color: #4a5568; font-size: 16px; background: transparent;")
        grip.setFixedWidth(16)
        layout.addWidget(grip, 0, Qt.AlignVCenter)

        name = pack_info.get("name") or mod_id
        version = pack_info.get("version", "")

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("modName")
        top_row.addWidget(name_lbl)

        if version:
            ver_lbl = QLabel(f"v{version}")
            ver_lbl.setObjectName("modVersion")
            top_row.addWidget(ver_lbl)

        top_row.addStretch()
        info_col.addLayout(top_row)

        author = pack_info.get("author", "")
        if author:
            author_lbl = QLabel(author)
            author_lbl.setObjectName("modAuthor")
            info_col.addWidget(author_lbl)

        layout.addLayout(info_col, 1)

        detail_btn = QPushButton(tr("mod_manager.detail_btn"))
        detail_btn.setObjectName("secondaryButton")
        detail_btn.setFixedHeight(24)
        detail_btn.setCursor(Qt.PointingHandCursor)
        detail_btn.clicked.connect(self._show_detail)
        layout.addWidget(detail_btn, 0, Qt.AlignVCenter)

    def paintEvent(self, event) -> None:
        if self._issues:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(180, 130, 0, 46))
            painter.drawRoundedRect(self.rect(), 5, 5)
            painter.end()
        super().paintEvent(event)

    def _show_detail(self) -> None:
        dlg = ModDetailDialog(self.mod_id, self._pack_info, self._issues, self.window())
        dlg.exec()


class ModManagerTab(QWidget):
    """Mod 管理标签页主体。"""

    exit_requested: Signal = Signal()
    start_requested: Signal = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mods: list[tuple[str, dict]] = []
        self._issues: dict[str, list[str]] = {}
        self._known_mod_ids: list[str] = []
        self._init_ui()
        self._load_mods()

        self._hot_timer = QTimer(self)
        self._hot_timer.setInterval(1000)
        self._hot_timer.timeout.connect(self._hot_reload_check)
        self._hot_timer.start()

    # ── UI 初始化 ────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.info_label = QLabel("")
        self.info_label.setObjectName("info")
        layout.addWidget(self.info_label)

        list_container = QFrame()
        list_container.setObjectName("listContainer")
        lc_layout = QVBoxLayout(list_container)
        lc_layout.setContentsMargins(0, 0, 0, 0)
        lc_layout.setSpacing(0)

        self.mod_list = QListWidget()
        self.mod_list.setObjectName("packList")
        self.mod_list.setSelectionMode(QListWidget.SingleSelection)
        self.mod_list.setDragEnabled(True)
        self.mod_list.setAcceptDrops(True)
        self.mod_list.setDropIndicatorShown(True)
        self.mod_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.mod_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.mod_list.model().rowsMoved.connect(self._on_rows_moved)
        lc_layout.addWidget(self.mod_list)

        layout.addWidget(list_container, 1)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addStretch()

        exit_btn = QPushButton(tr("resource_selector.exit"))
        exit_btn.setObjectName("secondaryButton")
        exit_btn.clicked.connect(self.exit_requested.emit)
        footer.addWidget(exit_btn)

        start_btn = QPushButton(tr("resource_selector.start"))
        start_btn.setObjectName("primaryButton")
        start_btn.clicked.connect(self.start_requested.emit)
        footer.addWidget(start_btn)

        layout.addLayout(footer)

    # ── 热加载检测 ───────────────────────────────────────────────────────

    def _hot_reload_check(self) -> None:
        """定期扫描 mod/ 目录，有增减时自动刷新列表（保留已有排序）。"""
        try:
            from expansion.life.mod import LifeModRegistry
            registry = LifeModRegistry(mod_root="mod", protocol_version="0.3")
            mod_dirs = registry.discover()
            current_ids = []
            for mod_dir in mod_dirs:
                pack = registry.load_pack_info(mod_dir)
                if pack:
                    mod_id = str(pack.get("id") or mod_dir.name).strip()
                    current_ids.append(mod_id)
        except Exception:
            return

        if set(current_ids) == set(self._known_mod_ids):
            return

        _log.DEBUG("[ModTab]热加载：mod 目录有变化，刷新列表")
        self._load_mods()

    # ── 数据加载 ─────────────────────────────────────────────────────────

    def _load_mods(self) -> None:
        try:
            from expansion.life.mod import LifeModRegistry
            registry = LifeModRegistry(mod_root="mod", protocol_version="0.3")
            mod_dirs = registry.discover()
            self._issues = registry.validate()
            raw: list[tuple[str, dict]] = []
            for mod_dir in mod_dirs:
                pack = registry.load_pack_info(mod_dir)
                if pack:
                    mod_id = str(pack.get("id") or mod_dir.name).strip()
                    raw.append((mod_id, pack))
        except Exception as e:
            _log.WARN(f"[ModTab]扫描 mod 失败: {e}")
            raw = []

        saved_order = _read_order()
        if saved_order:
            order_map = {mid: pack for mid, pack in raw}
            ordered: list[tuple[str, dict]] = []
            for mid in saved_order:
                if mid in order_map:
                    ordered.append((mid, order_map[mid]))
            in_order = set(saved_order)
            for mid, pack in raw:
                if mid not in in_order:
                    ordered.append((mid, pack))
            self._mods = ordered
        else:
            self._mods = raw

        self._known_mod_ids = [mid for mid, _ in self._mods]
        self._render_list()

    # ── 列表渲染 ─────────────────────────────────────────────────────────

    def _render_list(self) -> None:
        self.mod_list.clear()
        if not self._mods:
            self.info_label.setText(tr("mod_manager.empty"))
            return

        self.info_label.setText(tr("mod_manager.count", total=len(self._mods)))

        for mod_id, pack in self._mods:
            issues = self._issues.get(mod_id, [])
            widget = ModListItem(mod_id, pack, issues)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, mod_id)
            has_author = bool(pack.get("author", ""))
            item.setSizeHint(QSize(0, 58 if has_author else 44))
            self.mod_list.addItem(item)
            self.mod_list.setItemWidget(item, widget)

    def _reassign_widgets(self) -> None:
        """拖拽后重建所有行的 Widget。"""
        mod_map = {mid: pack for mid, pack in self._mods}
        for i in range(self.mod_list.count()):
            item = self.mod_list.item(i)
            if item is None:
                continue
            mid = item.data(Qt.UserRole)
            pack = mod_map.get(mid, {})
            issues = self._issues.get(mid, [])
            widget = ModListItem(mid, pack, issues)
            has_author = bool(pack.get("author", ""))
            item.setSizeHint(QSize(0, 58 if has_author else 44))
            self.mod_list.setItemWidget(item, widget)

    # ── 拖拽回调 ─────────────────────────────────────────────────────────

    def stop_timers(self) -> None:
        """停止所有后台定时器（对话框关闭时调用）。"""
        self._hot_timer.stop()

    def _on_rows_moved(
        self, src_parent, src_start, src_end, dst_parent, dst_row
    ) -> None:
        """拖拽结束：同步顺序 → 重建 Widget → 自动保存至 mod/load_order.json。"""
        mod_map = {mid: pack for mid, pack in self._mods}
        new_mods: list[tuple[str, dict]] = []
        for i in range(self.mod_list.count()):
            item = self.mod_list.item(i)
            if item is None:
                continue
            mid = item.data(Qt.UserRole)
            if mid in mod_map:
                new_mods.append((mid, mod_map[mid]))
        self._mods = new_mods
        self._known_mod_ids = [mid for mid, _ in self._mods]
        self._reassign_widgets()

        order = [mid for mid, _ in self._mods]
        _write_order(order)
        _log.DEBUG(f"[ModTab]拖拽后自动保存顺序: {order}")
