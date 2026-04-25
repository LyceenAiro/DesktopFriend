from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ui.life_window.tabs.states_tab import HoverDetailProgressBar
from ui.setting.common import create_section_card
from util.i18n import tr


class LifeNutritionTab(QFrame):
    tab_name = tr("life.tabs.nutrition")

    def __init__(self, nutrition_definitions: list[dict] | None = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        nutrition_card = create_section_card(tr("life.nutrition.card.title"), tr("life.nutrition.card.desc"))
        card_layout = nutrition_card.layout()

        self._nutrition_defs = nutrition_definitions or []
        self.progress_rows: dict[str, HoverDetailProgressBar] = {}

        for nutrition_def in self._nutrition_defs:
            nutrition_id = str(nutrition_def.get("id") or "").strip()
            if not nutrition_id:
                continue

            i18n_key = str(nutrition_def.get("i18n_key") or f"life.nutrition.{nutrition_id}")
            fallback_name = str(nutrition_def.get("name") or nutrition_id)

            row_frame = QFrame()
            row_layout = QVBoxLayout(row_frame)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)

            top_row = QHBoxLayout()
            top_row.setSpacing(12)

            label = QLabel(tr(i18n_key, default=fallback_name))
            label.setObjectName("fieldLabel")
            label.setFixedWidth(88)
            top_row.addWidget(label)

            bar = HoverDetailProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(22)
            top_row.addWidget(bar, 1)
            row_layout.addLayout(top_row)

            card_layout.addWidget(row_frame)
            self.progress_rows[nutrition_id] = bar

        layout.addWidget(nutrition_card)
        layout.addStretch()

    def update_data(self, nutrition_snapshot: list[dict]) -> None:
        snapshot_map = {str(row.get("id")): row for row in nutrition_snapshot}

        for nutrition_def in self._nutrition_defs:
            nutrition_id = str(nutrition_def.get("id") or "").strip()
            if not nutrition_id or nutrition_id not in self.progress_rows:
                continue

            row = snapshot_map.get(nutrition_id, {})
            bar = self.progress_rows[nutrition_id]
            bar.set_state_payload(row)