from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ui.life_window.info_dialog import LifeInfoDialog
from ui.life_window.sub_tab_bar import PaginatedSubTabBar
from ui.setting.common import create_section_card
from util.i18n import tr


_OTHER_CLASS_ID = "__other__"


class LifeInventoryTab(QFrame):
    tab_name = tr("life.tabs.inventory")
    _CONTROL_HEIGHT = 28
    _SEARCH_STYLE = (
        "QLineEdit { background: #1f1f1f; color: #f0f0f0; border: 1px solid #3a3a3a; "
        "border-radius: 7px; padding: 0 10px; min-height: 26px; max-height: 26px; }"
        "QLineEdit:focus { border: 1px solid #5f8fc8; background: #252525; }"
        "QToolTip { background-color: #111820; color: #b9d7ee; "
        "border: 1px solid #2e4d6b; border-radius: 10px; padding: 8px 10px; }"
    )
    _FILTER_BTN_STYLE = (
        "QPushButton { background: #2b2b2b; color: #d0d0d0; border: 1px solid #3d3d3d; "
        "border-radius: 7px; padding: 0 10px; min-height: 26px; max-height: 26px; }"
        "QPushButton:hover { background: #343434; }"
        "QPushButton:checked { background: #1f5a9e; color: #ffffff; border: 1px solid #3f79c3; }"
    )

    def __init__(
        self,
        get_item_detail: Callable[[str], dict | None],
        get_item_effect_summary: Callable[[str], dict | None],
        use_item_with_count: Callable[[str, int, bool], bool],
        get_item_cooldown_remaining: Callable[[str], float],
        get_item_class_registry: Callable[[], dict[str, dict]],
        feedback_callback: Callable[[str, str], None],
        refresh_callback: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self._items: list[dict] = []
        self._developer_mode = False
        self._get_item_detail = get_item_detail
        self._get_item_effect_summary = get_item_effect_summary
        self._use_item_with_count = use_item_with_count
        self._get_item_cooldown_remaining = get_item_cooldown_remaining
        self._get_item_class_registry = get_item_class_registry
        self._feedback_callback = feedback_callback
        self._refresh_callback = refresh_callback
        self._rows: list[QFrame] = []
        self._active_class: str | None = None  # None = 全部
        self._search_text: str = ""
        self._usable_only: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        # 子标签栏
        self._sub_tab_bar = PaginatedSubTabBar(on_switch=self._switch_class, parent=self)
        layout.addWidget(self._sub_tab_bar)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(18, 0, 18, 0)
        filter_row.setSpacing(8)

        self._search_input = QLineEdit(self)
        self._search_input.setPlaceholderText(tr("life.search.simple_placeholder"))
        self._search_input.setToolTip(tr("life.search.advanced_tip"))
        self._search_input.setStyleSheet(self._SEARCH_STYLE)
        self._search_input.setFixedHeight(self._CONTROL_HEIGHT)
        self._search_input.textChanged.connect(self._on_search_changed)
        filter_row.addWidget(self._search_input, 1)

        self._usable_only_btn = QPushButton(tr("life.inventory.filter.usable_only"), self)
        self._usable_only_btn.setCheckable(True)
        self._usable_only_btn.setStyleSheet(self._FILTER_BTN_STYLE)
        self._usable_only_btn.setFixedHeight(self._CONTROL_HEIGHT)
        self._usable_only_btn.setFixedWidth(96)
        self._usable_only_btn.toggled.connect(self._on_usable_only_toggled)
        filter_row.addWidget(self._usable_only_btn)

        layout.addLayout(filter_row)

        inventory_card = create_section_card(tr("life.inventory.card.title"), tr("life.inventory.card.desc"))
        card_layout = inventory_card.layout()

        self.rows_container = QFrame()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(10)
        card_layout.addWidget(self.rows_container)

        layout.addWidget(inventory_card)
        layout.addStretch()

    def update_data(self, items: list[dict], developer_mode: bool = False) -> None:
        self._items = list(items)
        self._developer_mode = bool(developer_mode)
        self._rebuild_sub_tabs()
        self._rebuild_item_rows()

    def _rebuild_sub_tabs(self) -> None:
        class_registry = self._get_item_class_registry()
        present_classes: set[str] = set()
        has_other = False
        for item in self._items:
            classes = item.get("classes", [])
            if classes:
                for cls in classes:
                    present_classes.add(cls)
            else:
                has_other = True

        if not present_classes and not has_other:
            self._sub_tab_bar.set_buttons([])
            return

        items: list[tuple[str | None, str]] = [(None, tr("life.inventory.class.all"))]
        for cls_id in sorted(present_classes):
            cls_def = class_registry.get(cls_id, {})
            i18n_key = cls_def.get("name_i18n_key", f"life.item_class.{cls_id}")
            fallback = cls_def.get("name", cls_id)
            label = tr(i18n_key, default=fallback)
            items.append((cls_id, label))
        if has_other:
            items.append((_OTHER_CLASS_ID, tr("life.inventory.class.other")))

        self._sub_tab_bar.set_buttons(items)
        self._sub_tab_bar.set_active(self._active_class)

    def _switch_class(self, cls_id: str | None) -> None:
        self._active_class = cls_id
        self._rebuild_item_rows()

    def _get_filtered_items(self) -> list[dict]:
        if self._active_class is None:
            base = self._items
        elif self._active_class == _OTHER_CLASS_ID:
            base = [item for item in self._items if not item.get("classes", [])]
        else:
            base = [item for item in self._items if self._active_class in item.get("classes", [])]

        if self._usable_only:
            base = [item for item in base if self._is_item_currently_usable(item)]

        tokens = self._parse_search_tokens(self._search_text)
        if not tokens:
            return base

        return [item for item in base if self._match_item_query_tokens(item, tokens)]

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text or ""
        self._rebuild_item_rows()

    def _on_usable_only_toggled(self, checked: bool) -> None:
        self._usable_only = bool(checked)
        self._rebuild_item_rows()

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

    def _match_item_query_tokens(self, item: dict, tokens: list[tuple[str, str]]) -> bool:
        name = str(item.get("name", ""))
        desc = str(item.get("desc", ""))
        item_id = str(item.get("id", ""))

        for mode, query in tokens:
            if mode == "id":
                if not self._fuzzy_match(item_id, query):
                    return False
            elif mode == "detail":
                if not self._fuzzy_match(desc, query):
                    return False
            else:
                if not self._fuzzy_match(name, query):
                    return False
        return True

    def _is_item_currently_usable(self, item: dict) -> bool:
        usable = bool(item.get("usable", True))
        cooldown_remaining = float(item.get("cooldown_remaining", 0) or 0)
        on_cooldown = bool(item.get("on_cooldown", False)) or cooldown_remaining > 0
        count = int(item.get("count", 0) or 0)
        return usable and not on_cooldown and count > 0

    def _rebuild_item_rows(self) -> None:
        self._clear_rows()
        filtered = self._get_filtered_items()

        if not filtered:
            empty = QLabel(tr("life.inventory.empty"))
            empty.setObjectName("helperText")
            row = self._wrap_row_widget(empty)
            self.rows_layout.addWidget(row)
            self._rows.append(row)
            return

        for item in filtered:
            row = self._build_item_row(item)
            self.rows_layout.addWidget(row)
            self._rows.append(row)

    def _clear_rows(self) -> None:
        for row in self._rows:
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

    def _build_item_row(self, item: dict) -> QFrame:
        row = QFrame()
        row.setObjectName("lifeInventoryRow")
        row.setStyleSheet(
            """
            QFrame#lifeInventoryRow {
                background: #1f1f1f;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            QFrame#lifeInventoryRow QLabel {
                background: transparent;
                border: none;
            }
            """
        )

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.setSpacing(10)

        text_block = QVBoxLayout()
        text_block.setSpacing(3)

        title = QLabel(f"{item.get('name', item.get('id', 'unknown'))}  x{int(item.get('count', 0))}")
        title.setStyleSheet("font-weight: 700; color: #f3f3f3; background: transparent; border: none;")
        text_block.addWidget(title)

        details: list[str] = []
        if self._developer_mode:
            details.append(f"ID: {item.get('id', '')}")
        if not bool(item.get("usable", True)):
            details.append(tr("life.inventory.not_usable"))

        cooldown_remaining = float(item.get("cooldown_remaining", 0))
        on_cooldown = bool(item.get("on_cooldown", False)) or cooldown_remaining > 0

        if details:
            subtitle = QLabel(" | ".join(details))
            subtitle.setObjectName("helperText")
            subtitle.setStyleSheet("background: transparent; border: none;")
            text_block.addWidget(subtitle)

        row_layout.addLayout(text_block, 1)

        info_btn = QPushButton(tr("life.inventory.info"))
        info_btn.setFixedWidth(72)
        info_btn.setFixedHeight(self._CONTROL_HEIGHT)
        info_btn.clicked.connect(lambda: self._show_item_info(str(item.get("id", ""))))
        row_layout.addWidget(info_btn)

        if on_cooldown:
            use_btn = QPushButton(tr("life.inventory.use_cooldown_btn"))
            use_btn.setFixedWidth(72)
            use_btn.setFixedHeight(self._CONTROL_HEIGHT)
            use_btn.setStyleSheet(
                "QPushButton { background-color: #4a4020; color: #b8a060; "
                "border: 1px solid #6a5828; border-radius: 6px; }"
                "QPushButton:hover { background-color: #5a4e28; }"
                "QPushButton:pressed { background-color: #3a3018; }"
            )
        else:
            use_btn = QPushButton(tr("life.inventory.use"))
            use_btn.setObjectName("primaryButton")
            use_btn.setFixedWidth(72)
            use_btn.setFixedHeight(self._CONTROL_HEIGHT)
        use_btn.setEnabled(bool(item.get("usable", True)))
        use_btn.clicked.connect(lambda: self._use_one_item(str(item.get("id", ""))))
        row_layout.addWidget(use_btn)

        return row

    def _wrap_row_widget(self, widget) -> QFrame:
        row = QFrame()
        row.setObjectName("lifeInventoryRow")
        row.setStyleSheet("QFrame#lifeInventoryRow { background: #1f1f1f; border: 1px solid #3a3a3a; border-radius: 8px; }")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.addWidget(widget)
        return row

    def _show_item_info(self, item_id: str) -> None:
        detail = self._get_item_detail(item_id)
        if not detail:
            self._feedback_callback(tr("life.inventory.info_missing"), "error")
            return

        dialog = LifeInfoDialog(
            str(detail.get("name", "")),
            str(detail.get("desc", "")).strip(),
            debug_lines=self._build_item_debug_lines(detail, self._get_item_effect_summary(item_id)) if self._developer_mode else None,
            parent=self,
        )
        dialog.exec()

    def _build_item_debug_lines(self, detail: dict, summary: dict | None) -> list[str]:
        lines = [
            f"{tr('life.inventory.info.id')}: {detail.get('id', '')}",
            f"{tr('life.inventory.info.category')}: {detail.get('category', 'unknown')}",
            f"{tr('life.inventory.info.usable')}: {tr('life.common.yes') if detail.get('usable', True) else tr('life.common.no')}",
        ]

        if not summary:
            return lines

        def _format_entries(title_key: str, entries: list[dict], label_key: str = "i18n_key") -> None:
            if not entries:
                return
            lines.append(f"{tr(title_key)}:")
            for entry in entries:
                label = tr(str(entry.get(label_key, '')), default=str(entry.get('name') or entry.get('id') or ''))
                lines.append(f"- {label} {float(entry.get('delta', 0.0)):+g}")

        _format_entries("life.inventory.info.effect.states", list(summary.get("instant_states", [])))
        _format_entries("life.inventory.info.effect.attrs", list(summary.get("instant_attrs", [])))
        _format_entries("life.inventory.info.effect.nutrition", list(summary.get("nutrition", [])))

        periodic_entries = list(summary.get("periodic_states", []))
        if periodic_entries:
            lines.append(f"{tr('life.inventory.info.effect.periodic')}:")
            for entry in periodic_entries:
                label = tr(str(entry.get("i18n_key", "")), default=str(entry.get("name") or entry.get("id") or ""))
                rule_key = str(entry.get("rule", "add"))
                rule_label = tr(f"life.inventory.info.effect.rule.{rule_key}", default=rule_key)
                lines.append(
                    "- "
                    + tr(
                        "life.inventory.info.effect.periodic_row",
                        target=label,
                        delta=f"{float(entry.get('delta', 0.0)):+g}",
                        duration=int(entry.get("duration", 0)),
                        rule=rule_label,
                    )
                )

        caps = list(summary.get("caps", []))
        if caps:
            lines.append(f"{tr('life.inventory.info.effect.caps')}:")
            for entry in caps:
                cap_key = str(entry.get("key", ""))
                target_key = cap_key
                cap_type = ""
                if cap_key.endswith("_max2"):
                    target_key = cap_key[:-5]
                    cap_type = "max2"
                elif cap_key.endswith("_max"):
                    target_key = cap_key[:-4]
                    cap_type = "max"
                elif cap_key.endswith("_min"):
                    target_key = cap_key[:-4]
                    cap_type = "min"

                target_label = tr(f"life.state.{target_key}", default=target_key)
                cap_label = tr(f"life.inventory.info.effect.cap_type.{cap_type}", default=cap_key)
                lines.append(f"- {target_label} ({cap_label}): {entry.get('value', '')}")

        return lines

    def _use_one_item(self, item_id: str) -> None:
        remaining = self._get_item_cooldown_remaining(item_id)
        if remaining > 0:
            secs = int(remaining) + 1
            self._feedback_callback(tr("life.inventory.use_on_cooldown", seconds=secs), "warning")
            return
        if self._use_item_with_count(item_id, 1, True):
            self._feedback_callback(tr("life.inventory.use_success", count=1), "success")
            self._refresh_callback()
            return
        self._feedback_callback(tr("life.inventory.use_failed"), "error")
        self._refresh_callback()
