from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from module.life.runtime import get_life_system
from ui.life_window.common import attach_window_shadow, create_pin_icon, style_window_controls
from ui.setting.toast import AnimatedStatusToast
from ui.life_window.tabs import LifeAttrsTab, LifeCollectionTab, LifeEffectsTab, LifeEventsTab, LifeInventoryTab, LifeNutritionTab, LifeStatesTab
from ui.styles.css import (
    BOTTOM_BAR_STYLE,
    DIVIDER_STYLE,
    NAV_BUTTON_ACTIVE_STYLE,
    NAV_BUTTON_STYLE,
    NAV_FRAME_STYLE,
    SCROLL_AREA_STYLE,
    TOP_BAR_STYLE,
    WINDOW_SHELL_STYLE,
)
from ui.styles.dialog_theme import apply_adobe_dialog_theme, apply_frameless_window_theme
from ui.styles.fade_scrollarea import FadeScrollArea
from util.cfg import load_config
from util.i18n import tr
from util.life_utils import format_duration as _format_duration


class LifeWindow(QDialog):
    """养成面板主窗口，结构对齐 UnifiedSettingsWindow。"""

    def __init__(self, parent=None):
        super().__init__(None)
        self._owner = parent
        self.life = get_life_system()

        self._resizing = False
        self._dragging = False
        self._resize_start_pos = None
        self._drag_start_pos = None
        self._resize_grip_size = 10
        self._always_on_top = False

        self.active_tab = None
        self.tab_buttons = {}
        self.tab_widgets = {}
        self._initial_tip_pending = True

        debug_config = load_config("debug")
        self.developer_mode = bool(debug_config.get("developer_mode", False))
        self.toast_duration_ms = int(debug_config.get("toast_duration_ms", 10000))

        self.setWindowTitle(tr("menu.life"))
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setFixedSize(820, 600)
        self.setWindowFlags((self.windowFlags() & ~Qt.Tool) | Qt.Window | Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.setWindowFlag(Qt.Tool, False)
        self.setWindowFlag(Qt.Window, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._build_shell()
        self._register_tabs()

        apply_adobe_dialog_theme(self)
        apply_frameless_window_theme(self)
        style_window_controls(self.min_button, self.close_button, self.pin_button)
        self._update_pin_button_icon()

        self.switch_tab(LifeStatesTab.tab_name)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self.refresh_view)
        self._refresh_timer.start()

        self.refresh_view()

    def _build_shell(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(0)

        self.window_shell = QFrame(self)
        self.window_shell.setObjectName("windowShell")
        self.window_shell.setAttribute(Qt.WA_StyledBackground, True)
        outer_layout.addWidget(self.window_shell)

        attach_window_shadow(self.window_shell, self)
        self.window_shell.setStyleSheet(WINDOW_SHELL_STYLE)

        main_layout = QVBoxLayout(self.window_shell)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)

        self.top_bar = QFrame()
        self.top_bar.setStyleSheet(TOP_BAR_STYLE)
        self.top_bar.setFixedHeight(64)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(28, 12, 20, 12)
        top_layout.setSpacing(0)

        self.title_label = QLabel(tr("menu.life"))
        self.title_label.setObjectName("title")
        top_layout.addWidget(self.title_label, 0, Qt.AlignVCenter)

        # 死亡状态指示器（宠物死亡时显示）
        self._death_label = QLabel(tr("life.death.status_label", default="[已死亡]"))
        self._death_label.setStyleSheet(
            "color: #e06060; font-weight: 700; font-size: 13px; "
            "background: transparent; border: none; padding: 0 8px;"
        )
        self._death_label.setVisible(False)
        top_layout.addWidget(self._death_label, 0, Qt.AlignVCenter)

        top_layout.addStretch()

        self.pin_button = QPushButton()
        self.pin_button.setObjectName("pinButton")
        self.pin_button.setCheckable(True)
        self.pin_button.setFixedSize(40, 32)
        self.pin_button.setIconSize(QSize(18, 18))
        self.pin_button.setToolTip(tr("window.pin.tooltip"))
        self.pin_button.clicked.connect(self._toggle_always_on_top)
        top_layout.addWidget(self.pin_button, 0, Qt.AlignVCenter)

        self.min_button = QPushButton("−")
        self.min_button.setObjectName("minButton")
        self.min_button.setFixedSize(44, 32)
        self.min_button.clicked.connect(self.showMinimized)
        top_layout.addWidget(self.min_button, 0, Qt.AlignVCenter)

        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(44, 32)
        self.close_button.clicked.connect(self.close)
        top_layout.addWidget(self.close_button, 0, Qt.AlignVCenter)

        main_layout.addWidget(self.top_bar)

        divider = QFrame()
        divider.setStyleSheet(DIVIDER_STYLE)
        divider.setFixedHeight(1)
        main_layout.addWidget(divider)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.nav_frame = QFrame()
        self.nav_frame.setStyleSheet(NAV_FRAME_STYLE)
        self.nav_frame.setFixedWidth(180)

        nav_outer = QVBoxLayout(self.nav_frame)
        nav_outer.setContentsMargins(0, 0, 0, 0)
        nav_outer.setSpacing(0)

        self.nav_scroll = QScrollArea(self.nav_frame)
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { background: transparent; width: 4px; border: none; margin: 2px 0; }"
            "QScrollBar::handle:vertical { background: rgba(245,245,245,0.2); border-radius: 2px; min-height: 20px; }"
            "QScrollBar::handle:vertical:hover { background: rgba(245,245,245,0.4); }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: none; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
        )

        self.nav_scroll_content = QWidget()
        self.nav_layout = QVBoxLayout(self.nav_scroll_content)
        self.nav_layout.setContentsMargins(10, 10, 10, 10)
        self.nav_layout.setSpacing(4)
        self.nav_layout.addStretch()

        self.nav_scroll.setWidget(self.nav_scroll_content)
        nav_outer.addWidget(self.nav_scroll)
        content_layout.addWidget(self.nav_frame)

        self.scroll_area = FadeScrollArea()
        self.scroll_area.setStyleSheet(SCROLL_AREA_STYLE)
        self.scroll_area.setWidgetResizable(True)

        self.scroll_content = QFrame()
        self.scroll_content.setStyleSheet("QFrame { background-color: #262626; border: none; }")
        self.scroll_area.setWidget(self.scroll_content)
        content_layout.addWidget(self.scroll_area, 1)

        self.death_overlay = self._build_death_overlay()
        self.death_overlay.setVisible(False)
        content_layout.addWidget(self.death_overlay, 1)

        main_layout.addLayout(content_layout, 1)

        self.bottom_bar = QFrame()
        self.bottom_bar.setObjectName("bottomBar")
        self.bottom_bar.setStyleSheet(BOTTOM_BAR_STYLE)
        self.bottom_bar.setFixedHeight(60)
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(28, 12, 28, 12)
        bottom_layout.setSpacing(8)

        bottom_layout.addSpacing(4)
        bottom_layout.addStretch()

        refresh_button = QPushButton(tr("life.window.refresh"))
        refresh_button.clicked.connect(self.refresh_view)
        bottom_layout.addWidget(refresh_button)

        main_layout.addWidget(self.bottom_bar)
        self.status_toast = AnimatedStatusToast(self.window_shell)

        self._feedback_widgets = [
            self,
            self.window_shell,
            self.top_bar,
            self.title_label,
            self.nav_frame,
            self.scroll_area.viewport(),
            self.scroll_content,
            self.bottom_bar,
        ]

        for widget in self._feedback_widgets:
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

    def _register_tabs(self):
        state_definitions = self.life.get_state_definitions()
        nutrition_definitions = self.life.get_nutrition_definitions()
        self.tab_widgets = {
            LifeStatesTab.tab_name: LifeStatesTab(
                state_definitions=state_definitions,
                get_state_runtime_snapshot=self.life.get_state_runtime_snapshot,
            ),
            LifeNutritionTab.tab_name: LifeNutritionTab(nutrition_definitions=nutrition_definitions),
            LifeAttrsTab.tab_name: LifeAttrsTab(),
            LifeInventoryTab.tab_name: LifeInventoryTab(
                get_item_detail=self.life.get_item_detail,
                get_item_effect_summary=self.life.get_item_effect_summary,
                use_item_with_count=self.life.use_item_with_count,
                get_item_cooldown_remaining=self.life.get_item_cooldown_remaining,
                get_item_class_registry=self.life.get_item_class_registry,
                feedback_callback=self._set_feedback,
                refresh_callback=self.refresh_view,
                can_use_item_with_reason=self.life.can_use_item_with_reason,
                get_item_fail_message=self.life.get_item_fail_message,
            ),
            LifeEffectsTab.tab_name: LifeEffectsTab(
                get_effect_detail=self.life.get_effect_detail,
                get_buff_class_registry=self.life.get_buff_class_registry,
                get_buff_classes=self.life.get_buff_classes,
            ),
            LifeEventsTab.tab_name: LifeEventsTab(
                fire_trigger=self.life.fire_trigger,
                get_trigger_detail=self.life.get_event_trigger_detail,
                get_item_display_name=self.life.get_item_display_name,
                get_trigger_cooldown_remaining=self.life.get_trigger_cooldown_remaining,
                get_trigger_executing_remaining=self.life.get_trigger_executing_remaining,
                can_fire_trigger=self.life.can_fire_trigger,
                get_trigger_class_registry=self.life.get_trigger_class_registry,
                feedback_callback=self._set_feedback,
                refresh_callback=self.refresh_view,
                get_trigger_fail_message=self.life.get_trigger_fail_message,
            ),
            LifeCollectionTab.tab_name: LifeCollectionTab(
                get_collection_snapshot=self.life.get_collection_snapshot,
                get_item_detail=self.life.get_item_detail,
                get_effect_detail=self.life.get_effect_detail,
                get_trigger_detail=self.life.get_event_trigger_detail,
                get_outcome_detail=self.life.get_event_outcome_detail,
            ),
        }

        for tab_name in (
            LifeStatesTab.tab_name,
            LifeNutritionTab.tab_name,
            LifeAttrsTab.tab_name,
            LifeInventoryTab.tab_name,
            LifeEffectsTab.tab_name,
            LifeEventsTab.tab_name,
            LifeCollectionTab.tab_name,
        ):
            btn = QPushButton(tab_name)
            btn.setFixedHeight(36)
            btn.setStyleSheet(NAV_BUTTON_STYLE)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked=False, name=tab_name: self.switch_tab(name))
            self.tab_buttons[tab_name] = btn
            self.nav_layout.insertWidget(self.nav_layout.count() - 1, btn)

        scroll_layout = QVBoxLayout(self.scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        for widget in self.tab_widgets.values():
            widget.setVisible(False)
            widget.setMouseTracking(True)
            widget.installEventFilter(self)
            scroll_layout.addWidget(widget)

    def switch_tab(self, tab_name: str):
        for name, btn in self.tab_buttons.items():
            btn.setStyleSheet(NAV_BUTTON_ACTIVE_STYLE if name == tab_name else NAV_BUTTON_STYLE)

        for widget in self.tab_widgets.values():
            widget.setVisible(False)

        if tab_name in self.tab_widgets:
            self.tab_widgets[tab_name].setVisible(True)

        self.active_tab = tab_name
        self._set_feedback()

    def _set_feedback(self, message: str = "", level: str = "info") -> None:
        if not message:
            self.status_toast.dismiss(animated=True)
            return
        self.status_toast.set_hide_duration(self.toast_duration_ms)
        self.status_toast.show_message(message, level, self.toast_duration_ms)

    def _toggle_always_on_top(self, checked: bool) -> None:
        self._always_on_top = bool(checked)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self._always_on_top)
        self._update_pin_button_icon()
        self.show()
        self.raise_()
        self.activateWindow()

    def _update_pin_button_icon(self) -> None:
        color = "#ffffff" if self._always_on_top else "#dcdcdc"
        self.pin_button.setIcon(create_pin_icon(color, active=self._always_on_top))

    def refresh_view(self):
        # --- 死亡状态处理 ---
        # 若 HP 已被外部（调试/重置）恢复到 > 0，自动执行复活
        if self.life.is_dead:
            hp = float(self.life.profile.states.get("hp", 0.0))
            if hp > 0:
                self.life.revive()
            else:
                self._show_death_indicator(True)

        # 正常 UI 始终可见（死亡时保持标签页可交互，效果列表能正常显示死亡 buff）
        self.nav_frame.setVisible(True)
        self.scroll_area.setVisible(True)
        self.death_overlay.setVisible(False)
        # 未死亡时确保死亡指示器隐藏
        if not self.life.is_dead:
            self._show_death_indicator(False)

        completed_triggers = self.life.pop_completed_trigger_results()

        profile = self.life.profile
        nutrition = self.life.get_nutrition_snapshot()
        items = self.life.get_inventory_snapshot()
        effects = list(profile.active_effects)
        triggers = self.life.get_event_triggers_snapshot()
        recent_event_logs = self.life.get_recent_event_logs()
        tag_display_map = self.life.get_tag_display_map()
        collection_snapshot = self.life.get_collection_snapshot()

        states_tab = self.tab_widgets.get(LifeStatesTab.tab_name)
        nutrition_tab = self.tab_widgets.get(LifeNutritionTab.tab_name)
        attrs_tab = self.tab_widgets.get(LifeAttrsTab.tab_name)
        inventory_tab = self.tab_widgets.get(LifeInventoryTab.tab_name)
        effects_tab = self.tab_widgets.get(LifeEffectsTab.tab_name)
        events_tab = self.tab_widgets.get(LifeEventsTab.tab_name)
        collection_tab = self.tab_widgets.get(LifeCollectionTab.tab_name)

        if states_tab is not None:
            states_tab.update_data(profile)
        if nutrition_tab is not None:
            nutrition_tab.update_data(nutrition)
        if attrs_tab is not None:
            attrs_tab.update_data(self.life.get_attr_snapshot())
            attrs_tab.update_level(self.life.get_level_snapshot())
        if collection_tab is not None:
            collection_tab.update_data(collection_snapshot, self.developer_mode)

        # 智能刷新：数据有变化时始终更新（包括当前在该标签页时），无变化时仅在非当前标签页时更新
        current_item_sig = tuple((i["id"], i["count"], i.get("on_cooldown", False)) for i in items)
        current_effect_sig = tuple(e.effect_id for e in effects)
        current_trigger_sig = tuple((t["id"], t.get("on_cooldown"), t.get("can_fire"), t.get("executing")) for t in triggers)
        current_event_log_sig = tuple(
            (
                int(r.get("seq", 0)) if isinstance(r.get("seq"), int) else 0,
                str(r.get("type", "")),
                str(r.get("source", "")),
                str(r.get("trigger_id", "")),
                str(r.get("trigger_name", "")),
                str((r.get("entry") or {}).get("type", "")) if isinstance(r.get("entry"), dict) else "",
                str((r.get("entry") or {}).get("id", "")) if isinstance(r.get("entry"), dict) else "",
            )
            for r in recent_event_logs
            if isinstance(r, dict)
        )
        inv_changed = current_item_sig != getattr(self, "_last_item_sig", None)
        eff_changed = current_effect_sig != getattr(self, "_last_effect_sig", None)
        trg_changed = current_trigger_sig != getattr(self, "_last_trigger_sig", None)
        event_log_changed = current_event_log_sig != getattr(self, "_last_event_log_sig", None)

        if inventory_tab is not None:
            if inv_changed or self.active_tab != LifeInventoryTab.tab_name:
                inventory_tab.update_data(items, self.developer_mode, tag_display_map)
                self._last_item_sig = current_item_sig

        if effects_tab is not None:
            if eff_changed or self.active_tab != LifeEffectsTab.tab_name:
                effects_tab.update_data(effects, self.developer_mode)
                self._last_effect_sig = current_effect_sig

        if events_tab is not None:
            if completed_triggers or trg_changed or event_log_changed or self.active_tab != LifeEventsTab.tab_name:
                events_tab.update_data(triggers, self.developer_mode, tag_display_map, recent_event_logs)
                self._last_trigger_sig = current_trigger_sig
                self._last_event_log_sig = current_event_log_sig

        # 任意标签页都提示“执行完成”
        if completed_triggers:
            latest_name = str(completed_triggers[-1].get("trigger_name", "")).strip() or str(
                completed_triggers[-1].get("trigger_id", "")
            )
            self._set_feedback(tr("life.events.completed", name=latest_name), "info")

    def _is_in_resize_zone(self, local_pos) -> bool:
        return local_pos.y() >= self.height() - self._resize_grip_size

    def _build_death_overlay(self) -> QFrame:
        """构建死亡覆盖层（静态结构，动态标签在 _update_death_overlay 中更新）。"""
        overlay = QFrame()
        overlay.setStyleSheet("QFrame { background-color: #262626; border: none; }")

        outer = QVBoxLayout(overlay)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        center = QFrame()
        center.setStyleSheet("QFrame { background: transparent; border: none; }")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(40, 32, 40, 32)
        center_layout.setSpacing(10)
        center_layout.setAlignment(Qt.AlignCenter)

        # 十字标记代替 emoji
        cross_label = QLabel("✦")
        cross_label.setAlignment(Qt.AlignCenter)
        cross_label.setStyleSheet(
            "font-size: 36px; color: #e06060; background: transparent; border: none; letter-spacing: 4px;"
        )
        center_layout.addWidget(cross_label)

        center_layout.addSpacing(4)

        title_label = QLabel(tr("life.death.title"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #e06060; background: transparent; border: none; letter-spacing: 1px;"
        )
        center_layout.addWidget(title_label)

        subtitle_label = QLabel(tr("life.death.subtitle"))
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 12px; color: #777; background: transparent; border: none;")
        center_layout.addWidget(subtitle_label)

        center_layout.addSpacing(20)

        self._death_playtime_label = QLabel("")
        self._death_playtime_label.setAlignment(Qt.AlignCenter)
        self._death_playtime_label.setStyleSheet(
            "font-size: 12px; color: #999; background: transparent; border: none;"
        )
        center_layout.addWidget(self._death_playtime_label)

        self._death_diedat_label = QLabel("")
        self._death_diedat_label.setAlignment(Qt.AlignCenter)
        self._death_diedat_label.setStyleSheet(
            "font-size: 12px; color: #999; background: transparent; border: none;"
        )
        center_layout.addWidget(self._death_diedat_label)

        center_layout.addSpacing(28)

        # 分割线
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setFixedWidth(200)
        divider.setStyleSheet("background-color: #3a3a3a; border: none;")
        center_layout.addWidget(divider, 0, Qt.AlignCenter)

        center_layout.addSpacing(12)

        hint_label = QLabel(tr("life.death.reset_hint"))
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("font-size: 11px; color: #555; background: transparent; border: none;")
        center_layout.addWidget(hint_label)

        outer.addWidget(center, 0, Qt.AlignHCenter)
        outer.addStretch(1)
        return overlay

    def _update_death_overlay(self) -> None:
        """用最新死亡摘要数据更新覆盖层标签。"""
        import datetime
        summary = self.life.get_death_summary()
        play_time_s = float(summary.get("play_time_s", 0))
        died_at = summary.get("died_at", 0)

        self._death_playtime_label.setText(
            tr("life.death.play_time", time=_format_duration(play_time_s))
        )
        if died_at:
            died_str = datetime.datetime.fromtimestamp(died_at).strftime("%Y-%m-%d %H:%M:%S")
            self._death_diedat_label.setText(tr("life.death.died_at", time=died_str))
        else:
            self._death_diedat_label.setText("")

    def _show_death_indicator(self, visible: bool) -> None:
        self._death_label.setVisible(visible)

    def _is_in_resize_zone(self, local_pos) -> bool:
        return local_pos.y() >= self.height() - self._resize_grip_size

    def _map_event_pos_to_self(self, watched, event):
        if not hasattr(event, "position"):
            return None
        return watched.mapTo(self, event.position().toPoint())

    def eventFilter(self, watched, event):
        if watched in self._feedback_widgets or watched in self.tab_widgets.values():
            local_pos = self._map_event_pos_to_self(watched, event)
            in_resize_zone = local_pos is not None and self._is_in_resize_zone(local_pos)

            if event.type() == QEvent.MouseMove:
                if self._resizing and self._resize_start_pos is not None:
                    delta = event.globalPosition().y() - self._resize_start_pos
                    new_height = max(460, min(self.height() + delta, 1200))
                    self.setFixedSize(self.width(), int(new_height))
                    self._resize_start_pos = event.globalPosition().y()
                    self.setCursor(QCursor(Qt.SizeVerCursor))
                    return True

                if self._dragging:
                    current_global = event.globalPosition().toPoint()
                    delta = current_global - self._drag_start_pos
                    self.move(self.pos() + delta)
                    self._drag_start_pos = current_global
                    return True

                self.setCursor(QCursor(Qt.SizeVerCursor if in_resize_zone else Qt.ArrowCursor))

            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if in_resize_zone:
                    self._resizing = True
                    self._resize_start_pos = event.globalPosition().y()
                    self.setCursor(QCursor(Qt.SizeVerCursor))
                    return True

                if watched in (self.top_bar, self.title_label):
                    self._dragging = True
                    self._drag_start_pos = event.globalPosition().toPoint()
                    return True

            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._resizing = False
                self._resize_start_pos = None
                self._dragging = False
                self._drag_start_pos = None
                self.setCursor(QCursor(Qt.SizeVerCursor if in_resize_zone else Qt.ArrowCursor))

        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "status_toast"):
            self.status_toast.reposition()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "status_toast"):
            self.status_toast.reposition()
        if self._initial_tip_pending:
            self._initial_tip_pending = False
