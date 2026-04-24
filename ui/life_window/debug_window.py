from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from ui.styles.fade_scrollarea import FadeScrollArea

from module.life.runtime import get_life_system
from ui.life_window.common import attach_window_shadow, create_pin_icon, style_window_controls
from ui.setting.common import create_section_card
from ui.setting.toast import AnimatedStatusToast
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
from util.cfg import load_config
from util.i18n import tr


class LifeDebugWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(None)
        self._owner = parent
        self.life = get_life_system()
        self._resizing = False
        self._resize_edge = None
        self._resize_start_pos = None
        self._resize_start_size = None
        self._resize_grip_size = 10
        self._dragging = False
        self._drag_start = None
        self.active_tab = ""
        self._always_on_top = False
        self._feedback_widgets: list[QFrame | QDialog | QLabel | QScrollArea] = []
        self.tab_buttons: dict[str, QPushButton] = {}
        self.tab_widgets: dict[str, QFrame] = {}
        self._initial_tip_pending = True
        debug_config = load_config("debug")
        self.toast_duration_ms = int(debug_config.get("toast_duration_ms", 10000))

        self.setWindowTitle(tr("life.debug.title"))
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setMinimumSize(820, 600)
        self.resize(820, 600)
        self.setWindowFlags((self.windowFlags() & ~Qt.Tool) | Qt.Window | Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.setWindowFlag(Qt.Tool, False)
        self.setWindowFlag(Qt.Window, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        shell = QFrame(self)
        shell.setObjectName("windowShell")
        shell.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(shell)
        attach_window_shadow(shell, self)

        root = QVBoxLayout(shell)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        self.header_bar = QFrame(shell)
        self.header_bar.setObjectName("topBar")
        self.header_bar.setFixedHeight(58)
        self.header_bar.setStyleSheet(TOP_BAR_STYLE)
        header_row = QHBoxLayout(self.header_bar)
        header_row.setContentsMargins(20, 10, 16, 10)
        header_row.setSpacing(8)

        self._title_label = QLabel(tr("life.debug.titlebar"))
        self._title_label.setObjectName("title")
        header_row.addWidget(self._title_label)
        header_row.addStretch()

        self.pin_button = QPushButton()
        self.pin_button.setObjectName("pinButton")
        self.pin_button.setCheckable(True)
        self.pin_button.setFixedSize(40, 32)
        self.pin_button.setIconSize(QSize(18, 18))
        self.pin_button.setToolTip(tr("window.pin.tooltip"))
        self.pin_button.clicked.connect(self._toggle_always_on_top)
        header_row.addWidget(self.pin_button, 0, Qt.AlignVCenter)

        self.min_button = QPushButton("−")
        self.min_button.setObjectName("minButton")
        self.min_button.setFixedSize(44, 32)
        self.min_button.clicked.connect(self.showMinimized)
        header_row.addWidget(self.min_button, 0, Qt.AlignVCenter)

        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(44, 32)
        self.close_button.clicked.connect(self.close)
        header_row.addWidget(self.close_button, 0, Qt.AlignVCenter)
        root.addWidget(self.header_bar)

        divider = QFrame()
        divider.setStyleSheet(DIVIDER_STYLE)
        divider.setFixedHeight(1)
        root.addWidget(divider)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.nav_frame = QFrame()
        self.nav_frame.setStyleSheet(NAV_FRAME_STYLE)
        self.nav_frame.setFixedWidth(200)
        self.nav_layout = QVBoxLayout(self.nav_frame)
        self.nav_layout.setContentsMargins(12, 12, 12, 12)
        self.nav_layout.setSpacing(8)
        content_layout.addWidget(self.nav_frame)

        self.scroll_area = FadeScrollArea()
        self.scroll_area.setStyleSheet(SCROLL_AREA_STYLE)
        self.scroll_area.setWidgetResizable(True)

        self.scroll_content = QFrame()
        self.scroll_content.setStyleSheet("QFrame { background-color: #262626; border: none; }")
        self.scroll_area.setWidget(self.scroll_content)
        content_layout.addWidget(self.scroll_area)
        root.addLayout(content_layout, 1)

        self.bottom_bar = QFrame(shell)
        self.bottom_bar.setObjectName("bottomBar")
        self.bottom_bar.setFixedHeight(60)
        self.bottom_bar.setStyleSheet(BOTTOM_BAR_STYLE)
        bottom_row = QHBoxLayout(self.bottom_bar)
        bottom_row.setContentsMargins(28, 12, 28, 12)
        bottom_row.setSpacing(8)
        bottom_row.addSpacing(4)
        bottom_row.addStretch()

        refresh_btn = QPushButton(tr("life.window.refresh"))
        refresh_btn.clicked.connect(self.refresh_view)
        bottom_row.addWidget(refresh_btn)
        root.addWidget(self.bottom_bar)
        self.status_toast = AnimatedStatusToast(shell)

        self._register_tabs()

        apply_adobe_dialog_theme(self)
        apply_frameless_window_theme(self)
        style_window_controls(self.min_button, self.close_button, self.pin_button)
        self._update_pin_button_icon()
        self.setStyleSheet(self.styleSheet() + WINDOW_SHELL_STYLE)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(500)
        self._refresh_timer.timeout.connect(self._refresh_on_timer)
        self._refresh_timer.start()

        self._feedback_widgets = [
            self,
            shell,
            self.header_bar,
            self._title_label,
            self.nav_frame,
            self.scroll_area.viewport(),
            self.scroll_content,
            self.bottom_bar,
        ]

        for widget in self._feedback_widgets:
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

        self.header_bar.installEventFilter(self)
        self._title_label.installEventFilter(self)
        self.installEventFilter(self)
        self.switch_tab(tr("life.debug.tabs.monitor"))
        self.refresh_view()

    def _register_tabs(self) -> None:
        self.tab_widgets = {
            tr("life.debug.tabs.monitor"): self._build_monitor_tab(),
            tr("life.debug.tabs.actions"): self._build_actions_tab(),
            tr("life.debug.tabs.effects"): self._build_effects_tab(),
            tr("life.debug.tabs.items"): self._build_items_tab(),
            tr("life.debug.tabs.values"): self._build_values_tab(),
            tr("life.debug.tabs.exp"): self._build_exp_tab(),
        }

        for tab_name in self.tab_widgets.keys():
            btn = QPushButton(tab_name)
            btn.setStyleSheet(NAV_BUTTON_STYLE)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked=False, name=tab_name: self.switch_tab(name))
            self.tab_buttons[tab_name] = btn
            self.nav_layout.addWidget(btn)

        self.nav_layout.addStretch()

        scroll_layout = QVBoxLayout(self.scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        for widget in self.tab_widgets.values():
            widget.setVisible(False)
            widget.installEventFilter(self)
            scroll_layout.addWidget(widget)

    def _build_monitor_tab(self) -> QFrame:
        root = QFrame()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        self.auto_refresh_checkbox = QCheckBox(tr("life.debug.auto_refresh"))
        self.auto_refresh_checkbox.setChecked(True)
        layout.addWidget(self.auto_refresh_checkbox, 0, Qt.AlignLeft)

        self.state_text = QTextEdit()
        self.state_text.setReadOnly(True)
        layout.addWidget(self.state_text, 1)
        return root

    def _build_actions_tab(self) -> QFrame:
        root = QFrame()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        card = create_section_card(tr("life.debug.card.runtime.title"), tr("life.debug.card.runtime.desc"))
        card_layout = card.layout()

        row = QHBoxLayout()
        row.setSpacing(8)
        tick_btn = QPushButton(tr("life.debug.tick_once"))
        tick_btn.clicked.connect(self._tick_once)
        row.addWidget(tick_btn)

        reload_btn = QPushButton(tr("life.debug.reload_json"))
        reload_btn.clicked.connect(self._reload)
        row.addWidget(reload_btn)

        save_btn = QPushButton(tr("common.save"))
        save_btn.clicked.connect(self._save)
        row.addWidget(save_btn)

        row.addStretch()

        card_layout.addLayout(row)
        layout.addWidget(card)

        collection_card = create_section_card(tr("life.debug.card.collection.title"), tr("life.debug.card.collection.desc"))
        collection_layout = collection_card.layout()
        collection_row = QHBoxLayout()
        collection_row.setSpacing(8)

        unlock_btn = QPushButton(tr("life.debug.unlock_all_collections"))
        unlock_btn.clicked.connect(self._unlock_all_collections)
        collection_row.addWidget(unlock_btn)
        collection_row.addStretch()
        collection_layout.addLayout(collection_row)
        layout.addWidget(collection_card)

        layout.addStretch()
        return root

    def _build_effects_tab(self) -> QFrame:
        root = QFrame()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        card = create_section_card(tr("life.debug.card.effects.title"), tr("life.debug.card.effects.desc"))
        card_layout = card.layout()

        apply_row = QHBoxLayout()
        apply_row.setSpacing(8)
        self.buff_combo = QComboBox()
        self.buff_combo.setEditable(True)
        self.buff_combo.setMinimumWidth(240)
        apply_row.addWidget(self.buff_combo)

        self.buff_duration_spin = QSpinBox()
        self.buff_duration_spin.setRange(1, 9999)
        self.buff_duration_spin.setValue(20)
        self.buff_duration_spin.setSuffix(" tick")
        apply_row.addWidget(self.buff_duration_spin)

        apply_btn = QPushButton(tr("settings.debug.life_apply_btn"))
        apply_btn.clicked.connect(self._apply_selected_buff)
        apply_row.addWidget(apply_btn)

        refresh_btn = QPushButton(tr("settings.debug.life_refresh"))
        refresh_btn.clicked.connect(self._reload_effect_selectors)
        apply_row.addWidget(refresh_btn)
        apply_row.addStretch()
        card_layout.addLayout(apply_row)

        clear_row = QHBoxLayout()
        clear_row.setSpacing(8)
        self.effect_combo = QComboBox()
        self.effect_combo.setEditable(True)
        self.effect_combo.setMinimumWidth(240)
        clear_row.addWidget(self.effect_combo)

        clear_btn = QPushButton(tr("settings.debug.life_clear_btn"))
        clear_btn.clicked.connect(self._clear_selected_effect)
        clear_row.addWidget(clear_btn)
        clear_row.addStretch()
        card_layout.addLayout(clear_row)

        layout.addWidget(card)
        layout.addStretch()
        return root

    def _build_items_tab(self) -> QFrame:
        root = QFrame()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        card = create_section_card(tr("life.debug.card.items.title"), tr("life.debug.card.items.desc"))
        card_layout = card.layout()

        give_row = QHBoxLayout()
        give_row.setSpacing(8)
        self.give_item_combo = QComboBox()
        self.give_item_combo.setEditable(True)
        self.give_item_combo.setMinimumWidth(220)
        give_row.addWidget(self.give_item_combo)

        self.give_item_count_spin = QSpinBox()
        self.give_item_count_spin.setRange(1, 9999)
        self.give_item_count_spin.setValue(5)
        give_row.addWidget(self.give_item_count_spin)

        give_btn = QPushButton(tr("life.debug.items.give"))
        give_btn.clicked.connect(self._give_item)
        give_row.addWidget(give_btn)
        give_row.addStretch()
        card_layout.addLayout(give_row)

        set_row = QHBoxLayout()
        set_row.setSpacing(8)
        self.set_item_combo = QComboBox()
        self.set_item_combo.setEditable(True)
        self.set_item_combo.setMinimumWidth(220)
        set_row.addWidget(self.set_item_combo)

        self.set_item_count_spin = QSpinBox()
        self.set_item_count_spin.setRange(0, 9999)
        self.set_item_count_spin.setValue(0)
        set_row.addWidget(self.set_item_count_spin)

        set_btn = QPushButton(tr("life.debug.items.set"))
        set_btn.clicked.connect(self._set_item_count)
        set_row.addWidget(set_btn)

        refresh_btn = QPushButton(tr("settings.debug.life_refresh"))
        refresh_btn.clicked.connect(self._reload_item_selectors)
        set_row.addWidget(refresh_btn)
        set_row.addStretch()
        card_layout.addLayout(set_row)

        layout.addWidget(card)
        layout.addStretch()
        return root

    def _build_values_tab(self) -> QFrame:
        root = QFrame()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        state_card = create_section_card(tr("life.debug.card.states.title"), tr("life.debug.card.states.desc"))
        state_layout = state_card.layout()
        state_row = QHBoxLayout()
        state_row.setSpacing(8)

        self.state_key_combo = QComboBox()
        self.state_key_combo.setMinimumWidth(220)
        self.state_key_combo.currentIndexChanged.connect(self._sync_value_editors_from_profile)
        state_row.addWidget(self.state_key_combo)

        self.state_value_spin = QDoubleSpinBox()
        self.state_value_spin.setRange(0.0, 999999.0)
        self.state_value_spin.setDecimals(2)
        self.state_value_spin.setSingleStep(1.0)
        self.state_value_spin.setFixedWidth(160)
        self.state_value_spin.setAlignment(Qt.AlignRight)
        state_row.addWidget(self.state_value_spin)

        set_state_btn = QPushButton(tr("life.debug.values.set_state"))
        set_state_btn.clicked.connect(self._set_state_value)
        state_row.addWidget(set_state_btn)
        state_row.addStretch()
        state_layout.addLayout(state_row)
        layout.addWidget(state_card)

        nutrition_card = create_section_card(tr("life.debug.card.nutrition.title"), tr("life.debug.card.nutrition.desc"))
        nutrition_layout = nutrition_card.layout()
        nutrition_row = QHBoxLayout()
        nutrition_row.setSpacing(8)

        self.nutrition_key_combo = QComboBox()
        self.nutrition_key_combo.setMinimumWidth(220)
        self.nutrition_key_combo.currentIndexChanged.connect(self._sync_value_editors_from_profile)
        nutrition_row.addWidget(self.nutrition_key_combo)

        self.nutrition_value_spin = QDoubleSpinBox()
        self.nutrition_value_spin.setRange(0.0, 999999.0)
        self.nutrition_value_spin.setDecimals(2)
        self.nutrition_value_spin.setSingleStep(1.0)
        self.nutrition_value_spin.setFixedWidth(160)
        self.nutrition_value_spin.setAlignment(Qt.AlignRight)
        nutrition_row.addWidget(self.nutrition_value_spin)

        set_nutrition_btn = QPushButton(tr("life.debug.values.set_nutrition"))
        set_nutrition_btn.clicked.connect(self._set_nutrition_value)
        nutrition_row.addWidget(set_nutrition_btn)
        nutrition_row.addStretch()
        nutrition_layout.addLayout(nutrition_row)
        layout.addWidget(nutrition_card)

        layout.addStretch()
        return root

    def _build_exp_tab(self) -> QFrame:
        root = QFrame()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        level_card = create_section_card(
            tr("life.debug.exp.set_level"), ""
        )
        level_layout = level_card.layout()
        level_row = QHBoxLayout()
        level_row.setSpacing(8)

        self.debug_level_spin = QSpinBox()
        self.debug_level_spin.setRange(1, max(1, self.life.max_level))
        self.debug_level_spin.setFixedWidth(120)
        self.debug_level_spin.setAlignment(Qt.AlignRight)
        level_row.addWidget(self.debug_level_spin)

        set_level_btn = QPushButton(tr("life.debug.exp.set_level"))
        set_level_btn.clicked.connect(self._debug_set_level)
        level_row.addWidget(set_level_btn)
        level_row.addStretch()
        level_layout.addLayout(level_row)
        layout.addWidget(level_card)

        exp_card = create_section_card(
            tr("life.debug.exp.set_exp"), ""
        )
        exp_layout = exp_card.layout()
        exp_row = QHBoxLayout()
        exp_row.setSpacing(8)

        self.debug_exp_spin = QDoubleSpinBox()
        self.debug_exp_spin.setRange(0.0, float(2 ** 31 - 1))
        self.debug_exp_spin.setDecimals(1)
        self.debug_exp_spin.setSingleStep(1.0)
        self.debug_exp_spin.setFixedWidth(160)
        self.debug_exp_spin.setAlignment(Qt.AlignRight)
        exp_row.addWidget(self.debug_exp_spin)

        set_exp_btn = QPushButton(tr("life.debug.exp.set_exp"))
        set_exp_btn.clicked.connect(self._debug_set_exp)
        exp_row.addWidget(set_exp_btn)
        exp_row.addStretch()
        exp_layout.addLayout(exp_row)
        layout.addWidget(exp_card)

        layout.addStretch()
        return root

    def switch_tab(self, tab_name: str) -> None:
        for name, btn in self.tab_buttons.items():
            btn.setStyleSheet(NAV_BUTTON_ACTIVE_STYLE if name == tab_name else NAV_BUTTON_STYLE)

        for widget in self.tab_widgets.values():
            widget.setVisible(False)

        if tab_name in self.tab_widgets:
            self.tab_widgets[tab_name].setVisible(True)
        self.active_tab = tab_name
        self._set_feedback()
        if tab_name == tr("life.debug.tabs.values"):
            self._sync_value_editors_from_profile()
        if tab_name == tr("life.debug.tabs.exp"):
            self._sync_exp_editors_from_profile()

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

    def _is_in_resize_zone(self, local_pos) -> bool:
        return self._get_resize_edge(local_pos) is not None

    def _get_resize_edge(self, local_pos):
        near_right = local_pos.x() >= self.width() - self._resize_grip_size
        near_bottom = local_pos.y() >= self.height() - self._resize_grip_size
        if near_right and near_bottom:
            return "corner"
        if near_right:
            return "right"
        if near_bottom:
            return "bottom"
        return None

    def _cursor_by_edge(self, edge):
        if edge == "corner":
            return Qt.SizeFDiagCursor
        if edge == "right":
            return Qt.SizeHorCursor
        if edge == "bottom":
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def _apply_resize_from_edge(self, global_pos):
        if self._resize_edge is None or self._resize_start_pos is None or self._resize_start_size is None:
            return

        delta = global_pos - self._resize_start_pos
        new_width = self._resize_start_size.width()
        new_height = self._resize_start_size.height()

        if self._resize_edge in ("right", "corner"):
            new_width = max(820, min(1600, self._resize_start_size.width() + delta.x()))
        if self._resize_edge in ("bottom", "corner"):
            new_height = max(600, min(1200, self._resize_start_size.height() + delta.y()))

        self.resize(int(new_width), int(new_height))

    def _map_event_pos_to_self(self, watched, event):
        if not hasattr(event, "position"):
            return None
        return watched.mapTo(self, event.position().toPoint())

    def eventFilter(self, watched, event):
        if watched in self._feedback_widgets or watched in self.tab_widgets.values():
            local_pos = self._map_event_pos_to_self(watched, event)
            resize_edge = self._get_resize_edge(local_pos) if local_pos is not None else None

            if event.type() == QEvent.MouseMove:
                if self._resizing:
                    self._apply_resize_from_edge(event.globalPosition().toPoint())
                    self.setCursor(QCursor(self._cursor_by_edge(self._resize_edge)))
                    return True

                if self._dragging and self._drag_start is not None:
                    current_global = event.globalPosition().toPoint()
                    delta = current_global - self._drag_start
                    self.move(self.pos() + delta)
                    self._drag_start = current_global
                    return True

                self.setCursor(QCursor(self._cursor_by_edge(resize_edge)))

            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if resize_edge is not None:
                    self._resizing = True
                    self._resize_edge = resize_edge
                    self._resize_start_pos = event.globalPosition().toPoint()
                    self._resize_start_size = self.size()
                    self.setCursor(QCursor(self._cursor_by_edge(resize_edge)))
                    return True

                if watched in (self.header_bar, self._title_label):
                    self._dragging = True
                    self._drag_start = event.globalPosition().toPoint()
                    return True

            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._resizing = False
                self._resize_edge = None
                self._resize_start_pos = None
                self._resize_start_size = None
                self._dragging = False
                self._drag_start = None
                self.setCursor(QCursor(self._cursor_by_edge(resize_edge)))
        return super().eventFilter(watched, event)

    def _refresh_on_timer(self):
        if self.auto_refresh_checkbox.isChecked():
            self.refresh_view(from_timer=True)

    def _is_spinbox_editing(self, spinbox: QDoubleSpinBox) -> bool:
        focus_widget = QApplication.focusWidget()
        if focus_widget is spinbox:
            return True
        line_edit = spinbox.lineEdit()
        if line_edit is not None and (focus_widget is line_edit or line_edit.hasFocus()):
            return True
        return spinbox.hasFocus()

    def _is_value_editor_busy(self) -> bool:
        return (
            self._is_spinbox_editing(self.state_value_spin)
            or self._is_spinbox_editing(self.nutrition_value_spin)
        )

    def _tick_once(self):
        self.life.tick()
        self.refresh_view()

    def _unlock_all_collections(self):
        self.life.unlock_all_collections()
        self._set_feedback(tr("life.debug.unlock_all_collections.done"), "success")
        self.refresh_view()

    def _apply_selected_buff(self):
        buff_id = str(self.buff_combo.currentText()).strip()
        if not buff_id:
            self._set_feedback(tr("settings.window.debug.life_effect.empty"), "error")
            return
        duration = int(self.buff_duration_spin.value())
        if self.life.apply_buff(buff_id, duration_override=max(1, duration)):
            self._set_feedback(
                tr("settings.window.debug.life_effect.applied", effect=f"{buff_id} ({duration} tick)"),
                "success",
            )
        else:
            self._set_feedback(tr("settings.window.debug.life_effect.apply_failed", effect=buff_id), "error")
        self.refresh_view()

    def _clear_selected_effect(self):
        effect_id = str(self.effect_combo.currentText()).strip()
        if not effect_id:
            self._set_feedback(tr("settings.window.debug.life_effect.empty"), "error")
            return
        if self.life.clear_effect(effect_id):
            self._set_feedback(tr("settings.window.debug.life_effect.cleared", effect=effect_id), "success")
        else:
            self._set_feedback(tr("settings.window.debug.life_effect.clear_failed", effect=effect_id), "info")
        self.refresh_view()

    def _give_item(self):
        item_id = str(self.give_item_combo.currentText()).strip()
        count = int(self.give_item_count_spin.value())
        if self.life.add_item(item_id, count):
            self._set_feedback(tr("life.debug.items.give_success", item=item_id, count=count), "success")
        else:
            self._set_feedback(tr("life.debug.items.give_failed", item=item_id), "error")
        self.refresh_view()

    def _set_item_count(self):
        item_id = str(self.set_item_combo.currentText()).strip()
        count = int(self.set_item_count_spin.value())
        if self.life.set_item_count(item_id, count):
            self._set_feedback(tr("life.debug.items.set_success", item=item_id, count=count), "success")
        else:
            self._set_feedback(tr("life.debug.items.set_failed", item=item_id), "error")
        self.refresh_view()

    def _set_state_value(self):
        state_id = str(self.state_key_combo.currentData() or self.state_key_combo.currentText()).strip()
        value = float(self.state_value_spin.value())
        if self.life.set_state_value(state_id, value):
            self._set_feedback(tr("life.debug.values.state_success", target=state_id, value=f"{value:.2f}"), "success")
        else:
            self._set_feedback(tr("life.debug.values.state_failed", target=state_id), "error")
        self.refresh_view()

    def _set_nutrition_value(self):
        nutrition_id = str(self.nutrition_key_combo.currentData() or self.nutrition_key_combo.currentText()).strip()
        value = float(self.nutrition_value_spin.value())
        if self.life.set_nutrition_value(nutrition_id, value):
            self._set_feedback(
                tr("life.debug.values.nutrition_success", target=nutrition_id, value=f"{value:.2f}"),
                "success",
            )
        else:
            self._set_feedback(tr("life.debug.values.nutrition_failed", target=nutrition_id), "error")
        self.refresh_view()

    def _reload(self):
        self.life.reload_registries()
        self._reload_effect_selectors()
        self._reload_item_selectors()
        self._reload_value_selectors()
        self._set_feedback(tr("life.debug.reload_done", "已重载注册表"), "success")
        self.refresh_view()

    def _save(self):
        self.life.save("default")
        self._set_feedback(tr("settings.window.feedback.saved"), "success")
        self.refresh_view()

    def _load(self):
        self.life.load("default")
        self._set_feedback(tr("life.debug.load_done", "已读取存档"), "success")
        self.refresh_view()

    def _reload_effect_selectors(self, force: bool = False):
        current_buff = self.buff_combo.currentText().strip() if hasattr(self, "buff_combo") else ""
        current_effect = self.effect_combo.currentText().strip() if hasattr(self, "effect_combo") else ""
        next_buff_ids = self.life.list_buff_ids()
        next_effect_ids = self.life.list_active_effect_ids()

        if not force:
            current_buff_ids = [self.buff_combo.itemText(i) for i in range(self.buff_combo.count())]
            current_effect_ids = [self.effect_combo.itemText(i) for i in range(self.effect_combo.count())]
            if current_buff_ids == next_buff_ids and current_effect_ids == next_effect_ids:
                return

        self.buff_combo.clear()
        self.buff_combo.addItems(next_buff_ids)
        if current_buff:
            self.buff_combo.setCurrentText(current_buff)

        self.effect_combo.clear()
        self.effect_combo.addItems(next_effect_ids)
        if current_effect:
            self.effect_combo.setCurrentText(current_effect)

    def _reload_item_selectors(self, force: bool = False):
        item_ids = self.life.list_item_ids()
        current_give = self.give_item_combo.currentText().strip() if hasattr(self, "give_item_combo") else ""
        current_set = self.set_item_combo.currentText().strip() if hasattr(self, "set_item_combo") else ""

        if not force:
            current_ids = [self.give_item_combo.itemText(i) for i in range(self.give_item_combo.count())]
            if current_ids == item_ids:
                return

        self.give_item_combo.clear()
        self.give_item_combo.addItems(item_ids)
        if current_give:
            self.give_item_combo.setCurrentText(current_give)

        self.set_item_combo.clear()
        self.set_item_combo.addItems(item_ids)
        if current_set:
            self.set_item_combo.setCurrentText(current_set)

    def _reload_value_selectors(self, force: bool = False):
        next_state_ids = list(self.life.state_keys)
        next_nutrition_ids = list(self.life.nutrition_keys)
        current_state = str(self.state_key_combo.currentData() or self.state_key_combo.currentText()).strip()
        current_nutrition = str(self.nutrition_key_combo.currentData() or self.nutrition_key_combo.currentText()).strip()

        if not force:
            current_state_ids = [self.state_key_combo.itemText(i) for i in range(self.state_key_combo.count())]
            current_nutrition_ids = [self.nutrition_key_combo.itemText(i) for i in range(self.nutrition_key_combo.count())]
            if current_state_ids == next_state_ids and current_nutrition_ids == next_nutrition_ids:
                return

        self.state_key_combo.clear()
        for state_id in next_state_ids:
            self.state_key_combo.addItem(state_id, state_id)
        if current_state:
            self.state_key_combo.setCurrentText(current_state)

        self.nutrition_key_combo.clear()
        for nutrition_id in next_nutrition_ids:
            self.nutrition_key_combo.addItem(nutrition_id, nutrition_id)
        if current_nutrition:
            self.nutrition_key_combo.setCurrentText(current_nutrition)

    def refresh_view(self, from_timer: bool = False):
        value_editor_busy = self._is_value_editor_busy() if from_timer else False

        self._reload_effect_selectors(force=not from_timer)
        self._reload_item_selectors(force=not from_timer)
        self._reload_value_selectors(force=(not from_timer) and (not value_editor_busy))

        # EXP tab 不参与自动刷新，只在切换进入时同步一次
        scroll = self.state_text.verticalScrollBar()
        prev_value = scroll.value()
        was_at_bottom = prev_value >= max(0, scroll.maximum() - 2)

        lines = [f"[{tr('life.debug.section.states')}]",]
        for row in self.life.get_state_runtime_snapshot():
            lines.append(
                f"{row['id']}: {float(row['value']):.2f} "
                f"(min={float(row['min']):.2f}, max={float(row['max']):.2f}, base_max={float(row['base_max']):.2f})"
            )
            lines.append(
                "  "
                + tr(
                    "life.debug.state.detail",
                    tick=f"{float(row['tick_delta']):+.2f}",
                    flat=f"{float(row['max_flat_delta']):+.2f}",
                    pct_net=f"{float(row['max_percent_net']):+.2f}%",
                    pct_add=f"{float(row['max_percent_add']):+.2f}%",
                    pct_sub=f"{float(row['max_percent_sub']):+.2f}%",
                )
            )

        lines.append(f"\n[{tr('life.debug.section.nutrition')}]")
        nutrition_rows = self.life.get_nutrition_snapshot()
        if not nutrition_rows:
            lines.append(tr("life.debug.empty"))
        else:
            for row in nutrition_rows:
                lines.append(
                    f"{row['name']} ({row['id']}): {row['value']:.2f} "
                    f"(min={row['min']:.2f}, max={row['max']:.2f}, decay={row['decay']:.2f})"
                )

        lines.append(f"\n[{tr('life.debug.section.attrs')}]")
        for k, v in self.life.profile.attrs.items():
            perm = self.life.profile.permanent_attr_delta.get(k, 0.0)
            level_bonus = self.life._compute_total_char_level_attr_bonus(k, self.life.profile.level) if hasattr(self.life, "_compute_total_char_level_attr_bonus") else 0.0
            extra = []
            if perm != 0.0:
                extra.append(f"perm={perm:+.2f}")
            if level_bonus != 0.0:
                extra.append(f"lv_bonus={level_bonus:+.2f}")
            suffix = f"  ({', '.join(extra)})" if extra else ""
            lines.append(f"{k}: {v:.2f}{suffix}")

        lines.append(f"\n[等级 / EXP]")
        snap = self.life.get_level_snapshot()
        lv = snap['level']
        max_lv = snap['max_level']
        exp = snap['exp']
        req = snap.get('exp_required')
        req_str = f"{req:.1f}" if req is not None else "满级"
        passive_exp = snap.get('passive_exp_per_tick', 0.0)
        lines.append(f"Lv.{lv} / {max_lv}  EXP: {exp:.1f} / {req_str}  (被动: +{passive_exp:.2f}/tick)")

        if self.life.profile.permanent_attr_delta:
            lines.append(f"\n[永久属性修正]")
            for k, v in self.life.profile.permanent_attr_delta.items():
                lines.append(f"{k}: {v:+.2f}")

        lines.append(f"\n[{tr('life.debug.section.inventory')}]")
        items = self.life.get_inventory_snapshot()
        if not items:
            lines.append(tr("life.debug.empty"))
        else:
            for row in items:
                lines.append(f"{row['name']} ({row['id']}): {row['count']}")

        lines.append(f"\n[{tr('life.debug.section.effects')}]")
        if not self.life.profile.active_effects:
            lines.append(tr("life.debug.empty"))
        else:
            for e in self.life.profile.active_effects:
                lines.append(f"{e.effect_id} [{e.source}] tick={e.remaining_ticks} rule={e.stack_rule} data={e.per_tick}")

        self.state_text.setPlainText("\n".join(lines))
        if self.auto_refresh_checkbox.isChecked() and was_at_bottom:
            scroll.setValue(scroll.maximum())
        else:
            scroll.setValue(min(prev_value, scroll.maximum()))

    def _sync_value_editors_from_profile(self):
        current_state_id = str(self.state_key_combo.currentData() or self.state_key_combo.currentText()).strip()
        if current_state_id in self.life.profile.states and not self._is_value_editor_busy():
            self.state_value_spin.setValue(float(self.life.profile.states[current_state_id]))

        current_nutrition_id = str(self.nutrition_key_combo.currentData() or self.nutrition_key_combo.currentText()).strip()
        if current_nutrition_id in self.life.profile.nutrition and not self._is_value_editor_busy():
            self.nutrition_value_spin.setValue(float(self.life.profile.nutrition[current_nutrition_id]))

    def _sync_exp_editors_from_profile(self):
        self.debug_level_spin.setRange(1, max(1, self.life.max_level))
        self.debug_level_spin.setValue(int(self.life.profile.level))
        self.debug_exp_spin.setValue(float(self.life.profile.exp))

    def _refresh_exp_status_label(self):
        pass  # 已移除状态标签，保留方法避免旧调用报错

    def _debug_set_level(self):
        level = int(self.debug_level_spin.value())
        self.life.set_level(level)
        self._set_feedback(f"Lv.{self.life.profile.level}", "success")
        self.refresh_view()

    def _debug_set_exp(self):
        exp = float(self.debug_exp_spin.value())
        self.life.set_exp(exp)
        self._set_feedback(f"EXP = {self.life.profile.exp:.1f}", "success")
        self.refresh_view()

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
