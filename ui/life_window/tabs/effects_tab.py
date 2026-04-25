from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QLabel, QPushButton, QVBoxLayout

from ui.life_window.info_dialog import LifeInfoDialog
from ui.life_window.sub_tab_bar import PaginatedSubTabBar
from ui.setting.common import create_section_card
from util.i18n import tr


_OTHER_CLASS_ID = "__other__"


class LifeEffectsTab(QFrame):
    tab_name = tr("life.tabs.effects")
    _CONTROL_HEIGHT = 28
    _SEARCH_STYLE = (
        "QLineEdit { background: #1f1f1f; color: #f0f0f0; border: 1px solid #3a3a3a; "
        "border-radius: 7px; padding: 0 10px; min-height: 26px; max-height: 26px; }"
        "QLineEdit:focus { border: 1px solid #5f8fc8; background: #252525; }"
        "QToolTip { background-color: #111820; color: #b9d7ee; "
        "border: 1px solid #2e4d6b; border-radius: 10px; padding: 8px 10px; }"
    )

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
        self._search_text: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        # 子标签栏
        self._sub_tab_bar = PaginatedSubTabBar(on_switch=self._switch_class, parent=self)
        layout.addWidget(self._sub_tab_bar)

        self._search_input = QLineEdit(self)
        self._search_input.setPlaceholderText(tr("life.search.simple_placeholder"))
        self._search_input.setToolTip(tr("life.search.advanced_tip"))
        self._search_input.setStyleSheet(self._SEARCH_STYLE)
        self._search_input.setFixedHeight(self._CONTROL_HEIGHT)
        self._search_input.textChanged.connect(self._on_search_changed)
        search_row = QHBoxLayout()
        search_row.setContentsMargins(18, 0, 18, 0)
        search_row.addWidget(self._search_input)
        layout.addLayout(search_row)

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
            base = self._effects
        elif self._active_class == _OTHER_CLASS_ID:
            base = [e for e in self._effects if not self._get_buff_classes(e.effect_id)]
        else:
            base = [e for e in self._effects if self._active_class in self._get_buff_classes(e.effect_id)]

        tokens = self._parse_search_tokens(self._search_text)
        if not tokens:
            return base

        return [e for e in base if self._match_effect_query_tokens(e, tokens)]

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text or ""
        self._rebuild_effect_rows()

    @staticmethod
    def _fuzzy_match(text: str, query: str) -> bool:
        source = (text or "").strip().lower()
        target = (query or "").strip().lower()
        if not target:
            return True
        idx = 0
        for ch in source:
            if idx < len(target) and ch == target[idx]:
                idx += 1
                if idx == len(target):
                    return True
        return False

    @staticmethod
    def _parse_search_tokens(text: str) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        for raw in (text or "").strip().split():
            mode = "name"
            body = raw
            if raw.startswith("@"):
                mode = "id"
                body = raw[1:]
            elif raw.startswith("#"):
                mode = "detail"
                body = raw[1:]

            body = body.replace("_", " ").strip()
            if not body:
                continue
            tokens.append((mode, body))
        return tokens

    def _match_effect_query_tokens(self, effect, tokens: list[tuple[str, str]]) -> bool:
        name = str(getattr(effect, "effect_name", "") or "")
        desc = str(getattr(effect, "effect_desc", "") or "")
        effect_id = str(getattr(effect, "effect_id", "") or "")

        for mode, query in tokens:
            if mode == "id":
                if not self._fuzzy_match(effect_id, query):
                    return False
            elif mode == "detail":
                if not self._fuzzy_match(desc, query):
                    return False
            else:
                if not self._fuzzy_match(name, query):
                    return False
        return True

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
            attr_mods = {k: v for k, v in getattr(effect, "attr_modifiers", {}).items()}
            data_parts: list[str] = []
            if per_tick:
                data_parts.append(f"tick={per_tick}")
            if attr_mods:
                data_parts.append(f"attrs={attr_mods}")
            data_str = ", ".join(data_parts) if data_parts else "—"
            subtitle = QLabel(
                tr(
                    "life.effects.row.detail",
                    tick=int(effect.remaining_ticks),
                    rule=str(effect.stack_rule),
                    data=data_str,
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

            attr_mods = {k: v for k, v in getattr(effect, "attr_modifiers", {}).items()}
            if attr_mods:
                debug_lines.append(f"{tr('life.effects.info.attr_modifiers', 'attr_modifiers')}: {attr_mods}")

            raw = detail.get("raw") if isinstance(detail.get("raw"), dict) else {}
            cap_lines: list[str] = []
            for key, value in raw.items():
                if not isinstance(key, str):
                    continue
                if key.endswith("_max2") or key.endswith("_max") or key.endswith("_min"):
                    cap_lines.append(f"- {key}: {value}")
            if cap_lines:
                debug_lines.append(f"{tr('life.inventory.info.effect.caps')}:")
                debug_lines.extend(cap_lines)

        dialog = LifeInfoDialog(
            effect_name, effect_desc, debug_lines,
            icon_base64=detail.get("icon_base64"),
            parent=self,
        )
        dialog.show()
