from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from ui.life_window.collection_dialog import CollectionDetailDialog
from ui.setting.common import create_section_card
from util.i18n import tr


class LifeCollectionTab(QFrame):
    """图鉴标签页：展示物品/效果/事件/结果的收集进度。"""

    tab_name = tr("life.tabs.collection")

    def __init__(
        self,
        get_collection_snapshot,
        get_item_detail=None,
        get_effect_detail=None,
        get_trigger_detail=None,
        get_outcome_detail=None,
        parent=None,
    ):
        super().__init__(parent)
        self._get_collection_snapshot = get_collection_snapshot
        self._get_item_detail = get_item_detail
        self._get_effect_detail = get_effect_detail
        self._get_trigger_detail = get_trigger_detail
        self._get_outcome_detail = get_outcome_detail

        self._progress_bars: dict[str, QProgressBar] = {}
        self._count_labels: dict[str, QLabel] = {}
        self._developer_mode = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QFrame()
        scroll_content.setObjectName("collectionTabContent")
        scroll_content.setStyleSheet("QFrame#collectionTabContent { background: transparent; }")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(12, 6, 12, 12)
        scroll_layout.setSpacing(12)

        categories = [
            ("items", tr("life.collection.items"), tr("life.collection.items_hint")),
            ("buffs", tr("life.collection.buffs"), tr("life.collection.buffs_hint")),
            ("triggers", tr("life.collection.triggers"), tr("life.collection.triggers_hint")),
            ("outcomes", tr("life.collection.outcomes"), tr("life.collection.outcomes_hint")),
        ]

        for key, title, hint in categories:
            card = self._build_category_card(key, title, hint)
            scroll_layout.addWidget(card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _build_category_card(self, key: str, title: str, hint: str) -> QFrame:
        card = create_section_card(title, hint)
        card.setObjectName("sectionCard")

        inner = card.layout()

        # 进度条
        progress = QProgressBar()
        progress.setFixedHeight(10)
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(False)
        progress.setStyleSheet("""
            QProgressBar {
                background: #1e1e1e; border: 1px solid #2a2a2a;
                border-radius: 5px; padding: 0px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a9eff, stop:1 #6c5ce7
                );
                border-radius: 4px;
            }
        """)
        inner.addWidget(progress)
        self._progress_bars[key] = progress

        # 计数 + 按钮行
        row = QHBoxLayout()
        row.setSpacing(12)

        count_lbl = QLabel(tr("life.collection.total_progress").format(unlocked=0, total=0))
        count_lbl.setStyleSheet("font-size: 13px; color: #9e9e9e; background: transparent; border: none;")
        row.addWidget(count_lbl)
        self._count_labels[key] = count_lbl

        row.addStretch()

        detail_btn = QPushButton(tr("life.collection.view_detail"))
        detail_btn.setObjectName("primaryButton")
        detail_btn.setFixedHeight(30)
        detail_btn.setStyleSheet("""
            QPushButton#primaryButton {
                font-size: 13px; padding: 0 16px;
                background: #e6453a; color: #fff;
                border: none; border-radius: 6px;
            }
            QPushButton#primaryButton:hover { background: #f95f53; }
            QPushButton#primaryButton:pressed { background: #d43a30; }
        """)
        detail_btn.clicked.connect(lambda checked, k=key: self._open_detail(k))
        row.addWidget(detail_btn)

        inner.addLayout(row)
        return card

    def update_data(self, snapshot: dict, developer_mode: bool = False) -> None:
        self._developer_mode = bool(developer_mode)
        if not snapshot:
            return
        for key in ("items", "buffs", "triggers", "outcomes"):
            data = snapshot.get(key, {})
            total = int(data.get("total", 0))
            unlocked = int(data.get("unlocked", 0))

            bar = self._progress_bars.get(key)
            if bar:
                pct = int(unlocked / total * 100) if total > 0 else 0
                bar.setValue(pct)

            lbl = self._count_labels.get(key)
            if lbl:
                lbl.setText(tr("life.collection.total_progress").format(unlocked=unlocked, total=total))

    def _open_detail(self, category_key: str):
        snapshot = self._get_collection_snapshot()
        data = snapshot.get(category_key, {})
        entries = data.get("entries", [])

        titles = {
            "items": tr("life.collection.items"),
            "buffs": tr("life.collection.buffs"),
            "triggers": tr("life.collection.triggers"),
            "outcomes": tr("life.collection.outcomes"),
        }
        category_name = titles.get(category_key, category_key)

        detail_callbacks = {
            "items": self._get_item_detail,
            "buffs": self._get_effect_detail,
            "triggers": self._get_trigger_detail,
            "outcomes": self._get_outcome_detail,
        }

        dialog = CollectionDetailDialog(
            category_name, entries,
            get_detail=detail_callbacks.get(category_key),
            developer_mode=self._developer_mode,
            parent=self,
        )
        dialog.exec()
