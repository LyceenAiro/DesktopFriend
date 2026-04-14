from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ui.life_window.tabs.states_tab import HoverDetailProgressBar
from ui.setting.common import create_section_card
from util.i18n import tr


class LifeNutritionTab(QFrame):
    tab_name = tr("life.tabs.nutrition")
    _MIN_VISIBLE_PERCENT = 4

    def __init__(self, nutrition_definitions: list[dict] | None = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        nutrition_card = create_section_card(tr("life.nutrition.card.title"), tr("life.nutrition.card.desc"))
        card_layout = nutrition_card.layout()

        self._nutrition_defs = nutrition_definitions or []
        self.progress_rows: dict[str, HoverDetailProgressBar] = {}
        self.detail_labels: dict[str, QLabel] = {}

        for nutrition_def in self._nutrition_defs:
            nutrition_id = str(nutrition_def.get("id") or "").strip()
            if not nutrition_id:
                continue

            i18n_key = str(nutrition_def.get("i18n_key") or f"life.nutrition.{nutrition_id}")
            fallback_name = str(nutrition_def.get("name") or nutrition_id)

            row_frame = QFrame()
            row_layout = QVBoxLayout(row_frame)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)

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

            detail_label = QLabel("")
            detail_label.setObjectName("helperText")
            detail_label.setWordWrap(True)
            row_layout.addWidget(detail_label)

            card_layout.addWidget(row_frame)
            self.progress_rows[nutrition_id] = bar
            self.detail_labels[nutrition_id] = detail_label

        layout.addWidget(nutrition_card)
        layout.addStretch()

    def update_data(self, nutrition_snapshot: list[dict]) -> None:
        snapshot_map = {str(row.get("id")): row for row in nutrition_snapshot}

        for nutrition_def in self._nutrition_defs:
            nutrition_id = str(nutrition_def.get("id") or "").strip()
            if not nutrition_id or nutrition_id not in self.progress_rows:
                continue

            row = snapshot_map.get(nutrition_id, {})
            value = float(row.get("value", nutrition_def.get("default", 0.0)))
            vmax = float(row.get("max", nutrition_def.get("max", 100.0)))
            decay = float(row.get("decay", nutrition_def.get("decay", 0.0)))
            safe_max = vmax if vmax > 0 else 1.0
            percent = int(round(max(0.0, min(1.0, value / safe_max)) * 100))
            if 0 < percent < self._MIN_VISIBLE_PERCENT:
                percent = self._MIN_VISIBLE_PERCENT

            self.progress_rows[nutrition_id].set_ratios(percent / 100.0, 1.0)
            self.progress_rows[nutrition_id].set_detail(f"{int(round(value))}/{int(round(vmax))}")

            matched_effects: list[str] = []
            for effect in list(nutrition_def.get("effects", [])):
                if not isinstance(effect, dict):
                    continue
                min_v = float(effect.get("min", float("-inf")))
                max_v = float(effect.get("max", float("inf")))
                if not (min_v <= value < max_v):
                    continue

                state_changes = []
                for state_key, delta in dict(effect.get("states", {})).items():
                    state_label = tr(f"life.state.{state_key}", default=str(state_key))
                    state_changes.append(f"{state_label} {delta:+g}")
                attr_changes = []
                for attr_key, delta in dict(effect.get("attrs", {})).items():
                    attr_label = tr(f"life.attr.{attr_key}", default=str(attr_key))
                    attr_changes.append(f"{attr_label} {delta:+g}")
                effect_parts = state_changes + attr_changes
                if effect_parts:
                    matched_effects.append(
                        tr(
                            "life.nutrition.effect.active",
                            range=f"[{int(round(min_v))}, {int(round(max_v))})",
                            effect=", ".join(effect_parts),
                        )
                    )

            if matched_effects:
                detail_text = tr(
                    "life.nutrition.row.detail.active",
                    decay=f"{decay:g}",
                    effects=" | ".join(matched_effects),
                )
            else:
                detail_text = tr("life.nutrition.row.detail", decay=f"{decay:g}")
            self.detail_labels[nutrition_id].setText(detail_text)