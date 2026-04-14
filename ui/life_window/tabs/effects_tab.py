from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ui.life_window.info_dialog import LifeInfoDialog
from ui.life_window.sub_tab_bar import PaginatedSubTabBar
from ui.setting.common import create_section_card
from util.i18n import tr


_OTHER_CLASS_ID = "__other__"


class LifeEffectsTab(QFrame):
    tab_name = tr("life.tabs.effects")

    def __init__(
        self,
        get_effect_detail: Callable[[str], dict | None],
        get_buff_class_registry: Callable[[], dict[str, dict[str, Any]]],
        get_buff_classes: Callable[[str], list[str]],
        parent=None,
    ):
        super().__init__(parent)
        self._effects: list = []
        self._developer_mode = False
        self._get_effect_detail = get_effect_detail
        self._get_buff_class_registry = get_buff_class_registry
        self._get_buff_classes = get_buff_classes
        self._rows: list[QFrame] = []
        self._active_class: str | None = None  # None = 全部

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        # 子标签栏
        self._sub_tab_bar = PaginatedSubTabBar(on_switch=self._switch_class, parent=self)
        layout.addWidget(self._sub_tab_bar)

        effects_card = create_section_card(tr("life.effects.card.title"), tr("life.effects.card.desc"))
        card_layout = effects_card.layout()

        self.rows_container = QFrame()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(10)
        card_layout.addWidget(self.rows_container)

        layout.addWidget(effects_card)
        layout.addStretch()

    def update_data(self, effects: list, developer_mode: bool = False) -> None:
        self._effects = list(effects)
        self._developer_mode = bool(developer_mode)
        self._rebuild_sub_tabs()
        self._rebuild_effect_rows()

    # ── 子标签 ──────────────────────────────────────────

    def _rebuild_sub_tabs(self) -> None:
        class_registry = self._get_buff_class_registry()
        present_classes: set[str] = set()
        has_other = False
        for effect in self._effects:
            classes = self._get_buff_classes(effect.effect_id)
            if classes:
                for cls in classes:
                    present_classes.add(cls)
            else:
                has_other = True

        if not present_classes and not has_other:
            self._sub_tab_bar.set_buttons([])
            return

        items: list[tuple[str | None, str]] = [(None, tr("life.effects.class.all"))]
        for cls_id in sorted(present_classes):
            cls_def = class_registry.get(cls_id, {})
            i18n_key = cls_def.get("name_i18n_key", f"life.buff_class.{cls_id}")
            fallback = cls_def.get("name", cls_id)
            label = tr(i18n_key, default=fallback)
            items.append((cls_id, label))
        if has_other:
            items.append((_OTHER_CLASS_ID, tr("life.effects.class.other")))

        self._sub_tab_bar.set_buttons(items)
        self._sub_tab_bar.set_active(self._active_class)

    def _switch_class(self, cls_id: str | None) -> None:
        self._active_class = cls_id
        self._rebuild_effect_rows()

    def _get_filtered_effects(self) -> list:
        if self._active_class is None:
            return self._effects
        if self._active_class == _OTHER_CLASS_ID:
            return [e for e in self._effects if not self._get_buff_classes(e.effect_id)]
        return [e for e in self._effects if self._active_class in self._get_buff_classes(e.effect_id)]

    # ── 效果行 ──────────────────────────────────────────

    def _rebuild_effect_rows(self) -> None:
        self._clear_rows()

        filtered = self._get_filtered_effects()

        if not filtered:
            empty = QLabel(tr("life.effects.empty"))
            empty.setObjectName("helperText")
            empty.setStyleSheet("background: transparent; border: none;")
            row = self._wrap_row_widget(empty)
            self.rows_layout.addWidget(row)
            self._rows.append(row)
            return

        for effect in filtered:
            row = self._build_effect_row(effect)
            self.rows_layout.addWidget(row)
            self._rows.append(row)

    def _clear_rows(self) -> None:
        for row in self._rows:
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

    def _build_effect_row(self, effect) -> QFrame:
        row = QFrame()
        row.setObjectName("lifeEffectRow")
        row.setStyleSheet(
            """
            QFrame#lifeEffectRow {
                background: #1f1f1f;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            QFrame#lifeEffectRow QLabel {
                background: transparent;
                border: none;
            }
            """
        )

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.setSpacing(10)
        row.setMinimumHeight(56)

        text_block = QVBoxLayout()
        text_block.setSpacing(3)

        title = QLabel(str(getattr(effect, "effect_name", effect.effect_id)))
        title.setStyleSheet("font-weight: 700; color: #f3f3f3; background: transparent; border: none;")
        text_block.addWidget(title)

        if self._developer_mode:
            per_tick = {k: int(round(float(v))) for k, v in effect.per_tick.items()}
            subtitle = QLabel(
                tr(
                    "life.effects.row.detail",
                    tick=int(effect.remaining_ticks),
                    rule=str(effect.stack_rule),
                    data=str(per_tick),
                )
            )
            subtitle.setObjectName("helperText")
            subtitle.setStyleSheet("background: transparent; border: none;")
            text_block.addWidget(subtitle)

        row_layout.addLayout(text_block, 1)

        info_btn = QPushButton(tr("life.effects.info"))
        info_btn.setFixedWidth(88)
        info_btn.clicked.connect(lambda: self._show_effect_info(effect))
        row_layout.addWidget(info_btn)

        return row

    def _wrap_row_widget(self, widget) -> QFrame:
        row = QFrame()
        row.setObjectName("lifeEffectRow")
        row.setStyleSheet(
            """
            QFrame#lifeEffectRow {
                background: #1f1f1f;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            QFrame#lifeEffectRow QLabel {
                background: transparent;
                border: none;
            }
            """
        )
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.addWidget(widget)
        row.setMinimumHeight(56)
        return row

    def _show_effect_info(self, effect) -> None:
        detail = self._get_effect_detail(str(effect.effect_id)) or {}
        effect_name = str(getattr(effect, "effect_name", "") or detail.get("name") or effect.effect_id)
        effect_desc = str(getattr(effect, "effect_desc", "") or detail.get("desc") or "").strip()

        debug_lines: list[str] = []
        per_tick = {k: int(round(float(v))) for k, v in effect.per_tick.items()}
        if self._developer_mode:
            debug_lines = [
                f"{tr('life.effects.info.id')}: {effect.effect_id}",
                f"source: {effect.source}",
                f"tick: {int(effect.remaining_ticks)}",
                f"rule: {effect.stack_rule}",
                f"data: {per_tick}",
            ]

        dialog = LifeInfoDialog(effect_name, effect_desc, debug_lines, self)
        dialog.exec()
