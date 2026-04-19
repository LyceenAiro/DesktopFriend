from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ui.life_window.info_dialog import LifeInfoDialog
from ui.life_window.sub_tab_bar import PaginatedSubTabBar
from ui.setting.common import create_section_card
from util.i18n import tr


_OTHER_CLASS_ID = "__other__"


class LifeEventsTab(QFrame):
    tab_name = tr("life.tabs.events")
    _MAX_GROUPED_RESULT_ROWS = 10
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
        fire_trigger: Callable[[str], dict[str, Any] | None],
        get_trigger_detail: Callable[[str], dict[str, Any] | None],
        get_item_display_name: Callable[[str], str],
        get_trigger_cooldown_remaining: Callable[[str], float],
        get_trigger_executing_remaining: Callable[[str], float],
        can_fire_trigger: Callable[[str], tuple[bool, str]],
        get_trigger_class_registry: Callable[[], dict[str, dict[str, Any]]],
        feedback_callback: Callable[[str, str], None],
        refresh_callback: Callable[[], None],
        get_trigger_fail_message: Callable[[str, str], str | None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._triggers: list[dict[str, Any]] = []
        self._developer_mode = False
        self._fire_trigger = fire_trigger
        self._get_trigger_detail = get_trigger_detail
        self._get_item_display_name = get_item_display_name
        self._get_trigger_cooldown_remaining = get_trigger_cooldown_remaining
        self._get_trigger_executing_remaining = get_trigger_executing_remaining
        self._can_fire_trigger = can_fire_trigger
        self._get_trigger_class_registry = get_trigger_class_registry
        self._feedback_callback = feedback_callback
        self._refresh_callback = refresh_callback
        self._get_trigger_fail_message = get_trigger_fail_message
        self._rows: list[QFrame] = []
        self._trigger_result_rows: list[QFrame] = []
        self._passive_result_rows: list[QFrame] = []
        self._event_logs: list[dict[str, Any]] = []
        self._active_class: str | None = None  # None = 全部
        self._search_text: str = ""
        self._triggerable_only: bool = False

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

        self._triggerable_only_btn = QPushButton(tr("life.events.filter.triggerable_only"), self)
        self._triggerable_only_btn.setCheckable(True)
        self._triggerable_only_btn.setStyleSheet(self._FILTER_BTN_STYLE)
        self._triggerable_only_btn.setFixedHeight(self._CONTROL_HEIGHT)
        self._triggerable_only_btn.setFixedWidth(96)
        self._triggerable_only_btn.toggled.connect(self._on_triggerable_only_toggled)
        filter_row.addWidget(self._triggerable_only_btn)

        layout.addLayout(filter_row)

        # 事件触发器卡片
        trigger_card = create_section_card(tr("life.events.card.title"), tr("life.events.card.desc"))
        card_layout = trigger_card.layout()

        self.rows_container = QFrame()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(10)
        card_layout.addWidget(self.rows_container)

        layout.addWidget(trigger_card)

        # 普通事件结果卡片
        trigger_result_card = create_section_card(
            tr("life.events.result.trigger.title"),
            tr("life.events.result.trigger.desc"),
        )
        trigger_result_card_layout = trigger_result_card.layout()

        self.trigger_result_container = QFrame()
        self.trigger_result_layout = QVBoxLayout(self.trigger_result_container)
        self.trigger_result_layout.setContentsMargins(0, 0, 0, 0)
        self.trigger_result_layout.setSpacing(6)
        trigger_result_card_layout.addWidget(self.trigger_result_container)
        layout.addWidget(trigger_result_card)

        # 随机事件结果卡片
        passive_result_card = create_section_card(
            tr("life.events.result.passive.title"),
            tr("life.events.result.passive.desc"),
        )
        passive_result_card_layout = passive_result_card.layout()

        self.passive_result_container = QFrame()
        self.passive_result_layout = QVBoxLayout(self.passive_result_container)
        self.passive_result_layout.setContentsMargins(0, 0, 0, 0)
        self.passive_result_layout.setSpacing(6)
        passive_result_card_layout.addWidget(self.passive_result_container)
        layout.addWidget(passive_result_card)
        layout.addStretch()

        self._render_event_logs()

    def update_data(
        self,
        triggers: list[dict[str, Any]],
        developer_mode: bool = False,
        tag_display_map: dict | None = None,
        recent_event_logs: list[dict[str, Any]] | None = None,
    ) -> None:
        self._triggers = list(triggers)
        self._developer_mode = bool(developer_mode)
        self._tag_display_map = tag_display_map or {}
        self._event_logs = list(recent_event_logs or [])
        self._rebuild_sub_tabs()
        self._rebuild_trigger_rows()
        self._render_event_logs()

    # ── 子标签 ──────────────────────────────────────────

    def _rebuild_sub_tabs(self) -> None:
        class_registry = self._get_trigger_class_registry()
        present_classes: set[str] = set()
        has_other = False
        for trigger in self._triggers:
            classes = trigger.get("classes", [])
            if classes:
                for cls in classes:
                    present_classes.add(cls)
            else:
                has_other = True

        if not present_classes and not has_other:
            self._sub_tab_bar.set_buttons([])
            return

        items: list[tuple[str | None, str]] = [(None, tr("life.events.class.all"))]
        for cls_id in sorted(present_classes):
            cls_def = class_registry.get(cls_id, {})
            i18n_key = cls_def.get("name_i18n_key", f"life.trigger_class.{cls_id}")
            fallback = cls_def.get("name", cls_id)
            label = tr(i18n_key, default=fallback)
            items.append((cls_id, label))
        if has_other:
            items.append((_OTHER_CLASS_ID, tr("life.events.class.other")))

        self._sub_tab_bar.set_buttons(items)
        self._sub_tab_bar.set_active(self._active_class)

    def _switch_class(self, cls_id: str | None) -> None:
        self._active_class = cls_id
        self._rebuild_trigger_rows()

    def _get_filtered_triggers(self) -> list[dict[str, Any]]:
        if self._active_class is None:
            base = self._triggers
        elif self._active_class == _OTHER_CLASS_ID:
            base = [t for t in self._triggers if not t.get("classes")]
        else:
            base = [t for t in self._triggers if self._active_class in t.get("classes", [])]

        if self._triggerable_only:
            base = [t for t in base if bool(t.get("can_fire", False))]

        tokens = self._parse_search_tokens(self._search_text)
        if not tokens:
            return base

        return [t for t in base if self._match_trigger_query_tokens(t, tokens)]

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text or ""
        self._rebuild_trigger_rows()

    def _on_triggerable_only_toggled(self, checked: bool) -> None:
        self._triggerable_only = bool(checked)
        self._rebuild_trigger_rows()

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

    def _match_trigger_query_tokens(self, trigger: dict[str, Any], tokens: list[tuple[str, str]]) -> bool:
        name = str(trigger.get("name", "") or "")
        desc = str(trigger.get("desc", "") or "")
        trigger_id = str(trigger.get("id", "") or "")

        for mode, query in tokens:
            if mode == "id":
                if not self._fuzzy_match(trigger_id, query):
                    return False
            elif mode == "detail":
                if not self._fuzzy_match(desc, query):
                    return False
            else:
                if not self._fuzzy_match(name, query):
                    return False
        return True

    # ── 触发器行 ────────────────────────────────────────

    def _rebuild_trigger_rows(self) -> None:
        for row in self._rows:
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        filtered = self._get_filtered_triggers()

        if not filtered:
            empty = QLabel(tr("life.events.empty"))
            empty.setObjectName("helperText")
            row = self._wrap_row(empty)
            self.rows_layout.addWidget(row)
            self._rows.append(row)
            return

        for trigger in filtered:
            row = self._build_trigger_row(trigger)
            self.rows_layout.addWidget(row)
            self._rows.append(row)

    def _build_trigger_row(self, trigger: dict[str, Any]) -> QFrame:
        row = QFrame()
        row.setObjectName("lifeEventRow")
        row.setStyleSheet(
            """
            QFrame#lifeEventRow {
                background: #1f1f1f;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            QFrame#lifeEventRow QLabel {
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

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title = QLabel(trigger.get("name", trigger.get("id", "unknown")))
        title.setStyleSheet("font-weight: 700; color: #f3f3f3; background: transparent; border: none;")
        title_row.addWidget(title)
        for tag_id in trigger.get("tags", []):
            tag_info = self._tag_display_map.get(tag_id)
            if tag_info:
                bubble = QLabel(tag_info["name"])
                color = tag_info["color"]
                bubble.setStyleSheet(
                    f"background: {color}33; color: #ffffff; border: 1px solid {color}66; "
                    "border-radius: 3px; padding: 0px 4px; font-size: 9px; font-weight: 600;"
                )
                title_row.addWidget(bubble)
        title_row.addStretch()
        text_block.addLayout(title_row)

        details: list[str] = []
        if self._developer_mode:
            details.append(f"ID: {trigger.get('id', '')}")

        cooldown_remaining = float(trigger.get("cooldown_remaining", 0))
        on_cooldown = bool(trigger.get("on_cooldown", False))
        executing = bool(trigger.get("executing", False))

        desc = trigger.get("desc", "")
        if desc:
            desc_label = QLabel(desc)
            desc_label.setObjectName("helperText")
            desc_label.setStyleSheet("color: #aaaaaa; background: transparent; border: none;")
            desc_label.setWordWrap(True)
            text_block.addWidget(desc_label)

        if details:
            subtitle = QLabel(" | ".join(details))
            subtitle.setObjectName("helperText")
            subtitle.setStyleSheet("background: transparent; border: none;")
            text_block.addWidget(subtitle)

        row_layout.addLayout(text_block, 1)

        # 详情按钮
        info_btn = QPushButton(tr("life.events.info"))
        info_btn.setFixedWidth(72)
        info_btn.setFixedHeight(self._CONTROL_HEIGHT)
        info_btn.clicked.connect(lambda: self._show_trigger_info(str(trigger.get("id", ""))))
        row_layout.addWidget(info_btn)

        # 触发按钮 — 与物品冷却一致：始终可点击，冷却/执行中时显示对应样式，点击时检查并toast提示
        busy_style = (
            "QPushButton { background-color: #4a4020; color: #b8a060; "
            "border: 1px solid #6a5828; border-radius: 6px; }"
            "QPushButton:hover { background-color: #5a4e28; }"
            "QPushButton:pressed { background-color: #3a3018; }"
        )
        blocked_style = (
            "QPushButton { background-color: #3a2020; color: #a06060; "
            "border: 1px solid #6a3828; border-radius: 6px; }"
            "QPushButton:hover { background-color: #4a2828; }"
            "QPushButton:pressed { background-color: #2a1818; }"
        )
        can_fire = bool(trigger.get("can_fire", True))
        block_reason = str(trigger.get("block_reason", ""))
        blocked = (not can_fire) and (not executing) and (not on_cooldown)
        if executing:
            fire_btn = QPushButton(tr("life.events.fire_executing_btn"))
            fire_btn.setFixedWidth(72)
            fire_btn.setFixedHeight(self._CONTROL_HEIGHT)
            fire_btn.setStyleSheet(busy_style)
        elif on_cooldown:
            fire_btn = QPushButton(tr("life.events.fire_cooldown_btn"))
            fire_btn.setFixedWidth(72)
            fire_btn.setFixedHeight(self._CONTROL_HEIGHT)
            fire_btn.setStyleSheet(busy_style)
        elif blocked:
            fire_btn = QPushButton(tr("life.events.fire_blocked_btn"))
            fire_btn.setFixedWidth(72)
            fire_btn.setFixedHeight(self._CONTROL_HEIGHT)
            fire_btn.setStyleSheet(blocked_style)
        else:
            fire_btn = QPushButton(tr("life.events.fire"))
            fire_btn.setObjectName("primaryButton")
            fire_btn.setFixedWidth(72)
            fire_btn.setFixedHeight(self._CONTROL_HEIGHT)
        fire_btn.clicked.connect(lambda: self._on_fire_trigger(str(trigger.get("id", ""))))
        row_layout.addWidget(fire_btn)

        return row

    def _wrap_row(self, widget) -> QFrame:
        row = QFrame()
        row.setObjectName("lifeEventRow")
        row.setStyleSheet("QFrame#lifeEventRow { background: #1f1f1f; border: 1px solid #3a3a3a; border-radius: 8px; }")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.addWidget(widget)
        return row

    def _on_fire_trigger(self, trigger_id: str) -> None:
        # 与物品冷却一致：点击时实时检查冷却和互斥
        remaining = self._get_trigger_cooldown_remaining(trigger_id)
        if remaining > 0:
            secs = int(remaining) + 1
            self._feedback_callback(tr("life.events.fire_on_cooldown", seconds=secs), "warning")
            return
        can, reason = self._can_fire_trigger(trigger_id)
        if not can:
            if reason == "dead":
                self._feedback_callback(tr("life.events.fire_dead"), "warning")
                return
            # 优先显示自定义失败文本（含标签限制 tag_restricted:{tag_id} 的注册表回查）
            if self._get_trigger_fail_message is not None:
                custom_msg = self._get_trigger_fail_message(trigger_id, reason)
                if custom_msg:
                    self._feedback_callback(custom_msg, "warning")
                    return
            if reason == "executing":
                exec_remaining = self._get_trigger_executing_remaining(trigger_id)
                if exec_remaining > 0:
                    secs = int(exec_remaining) + 1
                    self._feedback_callback(
                        tr("life.events.fire_executing_remaining", seconds=secs), "warning"
                    )
                else:
                    self._feedback_callback(tr("life.events.fire_executing"), "warning")
                return
            if reason.startswith("mutex:"):
                mutex_id = reason[6:]
                self._feedback_callback(tr("life.events.fire_mutex_blocked", trigger=mutex_id), "warning")
            elif reason.startswith("missing_item:"):
                item_id = reason[13:]
                item_name = self._get_item_display_name(item_id)
                self._feedback_callback(tr("life.events.fire_missing_item", item=item_name), "warning")
            elif reason.startswith("has_item:"):
                item_id = reason[9:]
                item_name = self._get_item_display_name(item_id)
                self._feedback_callback(tr("life.events.fire_has_item", item=item_name), "warning")
            elif reason.startswith("insufficient_state:"):
                state_key = reason[len("insufficient_state:"):].strip()
                state_name = tr(f"life.state.{state_key}", default=state_key or "state")
                self._feedback_callback(tr("life.events.fire_insufficient_state", state=state_name), "warning")
            else:
                self._feedback_callback(tr("life.events.fire_failed"), "error")
            return

        result = self._fire_trigger(trigger_id)
        if result is None:
            self._feedback_callback(tr("life.events.fire_failed"), "error")
            return

        if result.get("pending"):
            self._feedback_callback(
                tr("life.events.fire_started").replace("{name}", result.get("trigger_name", trigger_id)),
                "info",
            )
        else:
            self._feedback_callback(
                tr("life.events.fire_success").replace("{name}", result.get("trigger_name", trigger_id)),
                "info",
            )
        self._refresh_callback()

    def _render_event_logs(self) -> None:
        self._clear_result_rows(self.trigger_result_layout, self._trigger_result_rows)
        self._clear_result_rows(self.passive_result_layout, self._passive_result_rows)

        trigger_logs = [r for r in self._event_logs if str(r.get("source") or "") == "trigger"]
        passive_logs = [r for r in self._event_logs if str(r.get("source") or "") == "passive"]

        self._render_grouped_logs(self.trigger_result_layout, self._trigger_result_rows, trigger_logs, source="trigger")
        self._render_grouped_logs(self.passive_result_layout, self._passive_result_rows, passive_logs, source="passive")

    def _clear_result_rows(self, target_layout: QVBoxLayout, rows: list[QFrame]) -> None:
        for row in rows:
            target_layout.removeWidget(row)
            row.deleteLater()
        rows.clear()

    def _render_grouped_logs(
        self,
        target_layout: QVBoxLayout,
        row_store: list[QFrame],
        logs: list[dict[str, Any]],
        source: str,
    ) -> None:
        # 仅合并“相邻且同键”的记录，避免同类但不相邻的结果跨段合并。
        grouped_runs: list[dict[str, Any]] = []
        for log_row in reversed(logs):
            key = self._build_event_log_group_key(log_row)
            if grouped_runs and str(grouped_runs[-1].get("key", "")) == key:
                grouped_runs[-1]["count"] = int(grouped_runs[-1].get("count", 1)) + 1
            else:
                grouped_runs.append({"key": key, "row": log_row, "count": 1})

        if not grouped_runs:
            label = QLabel(tr("life.events.result.nothing"))
            label.setObjectName("helperText")
            row = self._wrap_row(label)
            target_layout.addWidget(row)
            row_store.append(row)
            return

        for payload in grouped_runs[: self._MAX_GROUPED_RESULT_ROWS]:
            repeat_count = int(payload["count"])
            text = self._format_event_log_text(payload["row"])
            entry_row = self._build_result_row(text, repeat_count, source=source)
            target_layout.addWidget(entry_row)
            row_store.append(entry_row)

    def _build_event_log_group_key(self, log_row: dict[str, Any]) -> str:
        log_type = str(log_row.get("type") or "")
        if log_type in {"pending", "completed"}:
            return f"{log_type}:{str(log_row.get('trigger_id') or '')}"
        entry = log_row.get("entry")
        if not isinstance(entry, dict):
            return f"unknown:{log_type}:{str(log_row)}"
        entry_type = str(entry.get("type") or "")
        entry_id = str(entry.get("id") or "")
        entry_count = int(entry.get("count", 1)) if str(entry.get("count", "")).strip() else 1
        return f"result:{entry_type}:{entry_id}:{entry_count}"

    def _build_result_row(self, text: str, repeat_count: int, source: str) -> QFrame:
        row = QFrame()
        row.setObjectName("lifeEventRow")
        row.setStyleSheet("QFrame#lifeEventRow { background: #1f1f1f; border: 1px solid #3a3a3a; border-radius: 8px; }")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.setSpacing(8)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: #d0d0d0; background: transparent; border: none;")
        row_layout.addWidget(label, 1)

        if repeat_count > 1:
            badge = QLabel(f"x{repeat_count}")
            badge_style = self._badge_style_for_source(source)
            badge.setStyleSheet(
                f"background: {badge_style['bg']}; color: #ffffff; border: 1px solid {badge_style['border']}; "
                "border-radius: 10px; padding: 1px 8px; font-weight: 700;"
            )
            badge.setAlignment(Qt.AlignCenter)
            row_layout.addWidget(badge, 0, Qt.AlignTop)

        return row

    def _badge_style_for_source(self, source: str) -> dict[str, str]:
        src = str(source or "").strip().lower()
        if src == "passive":
            return {"bg": "#1f6a6a", "border": "#4fa0a0"}
        return {"bg": "#2e5f9f", "border": "#5f8fc8"}

    def _format_event_log_text(self, log_row: dict[str, Any]) -> str:
        log_type = str(log_row.get("type") or "")
        trigger_name = str(log_row.get("trigger_name") or log_row.get("trigger_id") or "")
        ts_text = self._format_event_log_timestamp(log_row)

        if log_type == "pending":
            return f"[{ts_text}] {tr('life.events.result.pending').replace('{name}', trigger_name)}"
        if log_type == "completed":
            return f"[{ts_text}] {tr('life.events.completed', name=trigger_name)}"
        entry = log_row.get("entry")
        if not isinstance(entry, dict):
            return f"[{ts_text}] {str(log_row)}"
        entry_type = str(entry.get("type") or "")
        if entry_type == "outcome":
            text = f"🎲 {entry.get('name', entry.get('id', ''))}"
            desc = str(entry.get("desc") or "").strip()
            if desc:
                text += f" — {desc}"
            return f"[{ts_text}] {text}"
        if entry_type == "item":
            item_id = str(entry.get("id") or "")
            item_name = str(entry.get("name") or "").strip()
            if not item_name and item_id:
                item_name = self._get_item_display_name(item_id)
            display_name = item_name or item_id
            return f"[{ts_text}] 📦 {tr('life.events.result.got_item')}: {display_name} x{entry.get('count', 1)}"
        if entry_type == "buff":
            buff_name = str(entry.get("name") or entry.get("id") or "")
            return f"[{ts_text}] ✨ {tr('life.events.result.got_buff')}: {buff_name}"
        if entry_type == "none":
            return f"[{ts_text}] {tr('life.events.result.nothing')}"
        return f"[{ts_text}] {str(entry)}"

    def _format_event_log_timestamp(self, log_row: dict[str, Any]) -> str:
        try:
            ts = float(log_row.get("ts", 0.0))
        except Exception:
            ts = 0.0
        if ts <= 0.0:
            return "--:--:--"
        return datetime.fromtimestamp(ts).strftime("%H:%M:%S")

    def _show_trigger_info(self, trigger_id: str) -> None:
        detail = self._get_trigger_detail(trigger_id)
        if not detail:
            self._feedback_callback(tr("life.events.info_missing"), "error")
            return

        debug_lines = None
        if self._developer_mode:
            debug_lines = self._build_trigger_debug_lines(detail)

        desc = str(detail.get("desc", "")).strip()
        duration_s = detail.get("duration_s")
        try:
            dur_val = float(duration_s) if duration_s is not None else 0
        except Exception:
            dur_val = 0
        if dur_val > 0:
            dur_text = tr("life.events.info.duration", seconds=int(dur_val))
            desc = f"{desc}\n\n{dur_text}" if desc else dur_text

        dialog = LifeInfoDialog(
            str(detail.get("name", "")),
            desc,
            debug_lines=debug_lines,
            parent=self,
        )
        dialog.exec()

    def _build_trigger_debug_lines(self, detail: dict[str, Any]) -> list[str]:
        lines = [
            f"ID: {detail.get('id', '')}",
            f"{tr('life.events.debug.cooldown')}: {detail.get('cooldown_s', 0)}s",
            f"{tr('life.events.debug.duration')}: {detail.get('duration_s', 0)}s",
            f"{tr('life.events.debug.mutex')}: {', '.join(detail.get('mutex', [])) or '-'}",
        ]

        guaranteed = detail.get("guaranteed", {})
        if isinstance(guaranteed, dict):
            g_items = guaranteed.get("items", [])
            g_buffs = guaranteed.get("buffs", [])
            g_outcomes = guaranteed.get("outcomes", [])
            if g_items or g_buffs or g_outcomes:
                lines.append(f"{tr('life.events.debug.guaranteed')}:")
                for item in g_items:
                    if isinstance(item, dict):
                        lines.append(f"  {tr('life.events.result.got_item')}: {item.get('id', '')} x{item.get('count', 1)}")
                for buff in g_buffs:
                    bid = str(buff) if not isinstance(buff, dict) else str(buff.get("id", ""))
                    lines.append(f"  buff: {bid}")
                for outcome in g_outcomes:
                    oid = str(outcome) if not isinstance(outcome, dict) else str(outcome.get("id", ""))
                    lines.append(f"  outcome: {oid}")

        pools = detail.get("random_pools", [])
        if isinstance(pools, list):
            for pi, pool in enumerate(pools):
                if not isinstance(pool, dict):
                    continue
                entries = pool.get("entries", [])
                lines.append(f"{tr('life.events.debug.pool')} #{pi + 1} ({len(entries)} entries):")
                for entry in entries:
                    if isinstance(entry, dict):
                        lines.append(
                            f"  [{entry.get('type', '?')}] {entry.get('id', '?')} "
                            f"chance={entry.get('chance', 0)}%"
                        )

        return lines
