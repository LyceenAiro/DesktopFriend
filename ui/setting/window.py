import sys

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from ui.setting.tabs import AboutTab, BasicSettingsTab, DebugTab, LifeManagementTab, ModInfoTab, SmartConfigTab
from ui.setting.toast import AnimatedStatusToast
from ui.life_window.common import create_pin_icon
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
from util.log import _log
from util.cfg import load_config
from util.i18n import tr


class UnifiedSettingsWindow(QDialog):
    """统一设置窗口入口，只负责框架与标签页注册。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._resizing = False
        self._resize_edge = None
        self._dragging = False
        self._resize_start_pos = None
        self._resize_start_size = None
        self._drag_start_pos = None
        self._resize_grip_size = 10
        self._feedback_widgets = []
        self._always_on_top = False
        
        # 从配置文件加载toast时长
        debug_config = load_config("debug")
        self.toast_duration_ms = debug_config.get("toast_duration_ms", 10000)
        self.developer_mode = bool(debug_config.get("developer_mode", False))
        
        self.active_tab = None

        self.setWindowTitle(tr("settings.window.title"))
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setMinimumSize(820, 600)
        self.resize(820, 600)
        self.setWindowFlags((self.windowFlags() & ~Qt.Tool) | Qt.Window | Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._build_shell()
        self._register_tabs()

        apply_adobe_dialog_theme(self)
        apply_frameless_window_theme(self)
        self._apply_close_button_style()
        self._update_pin_button_icon()
        self._init_scrollbar_fade()
        self._init_mouse_feedback()

        self.switch_tab(BasicSettingsTab.tab_name)

    def _build_shell(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(0)

        self.window_shell = QFrame(self)
        self.window_shell.setObjectName("windowShell")
        self.window_shell.setAttribute(Qt.WA_StyledBackground, True)
        outer_layout.addWidget(self.window_shell)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 48))
        self.window_shell.setGraphicsEffect(shadow)
        self.window_shell.setStyleSheet(WINDOW_SHELL_STYLE)

        main_layout = QVBoxLayout(self.window_shell)
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)

        self.top_bar = QFrame()
        self.top_bar.setStyleSheet(TOP_BAR_STYLE)
        self.top_bar.setFixedHeight(64)
        top_bar_layout = QHBoxLayout(self.top_bar)
        top_bar_layout.setContentsMargins(28, 12, 20, 12)
        top_bar_layout.setSpacing(0)

        self.title_label = QLabel(tr("settings.window.title"))
        self.title_label.setObjectName("title")
        top_bar_layout.addWidget(self.title_label, 0, Qt.AlignVCenter)
        top_bar_layout.addStretch()

        self.pin_button = QPushButton()
        self.pin_button.setObjectName("pinButton")
        self.pin_button.setCheckable(True)
        self.pin_button.setFixedSize(40, 32)
        self.pin_button.setIconSize(QSize(18, 18))
        self.pin_button.setToolTip(tr("window.pin.tooltip"))
        self.pin_button.clicked.connect(self._toggle_always_on_top)
        top_bar_layout.addWidget(self.pin_button, 0, Qt.AlignVCenter)

        self.min_button = QPushButton("−")
        self.min_button.setObjectName("minButton")
        self.min_button.setFixedSize(44, 32)
        self.min_button.clicked.connect(self.showMinimized)
        top_bar_layout.addWidget(self.min_button, 0, Qt.AlignVCenter)

        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(44, 32)
        self.close_button.clicked.connect(self.close)
        top_bar_layout.addWidget(self.close_button, 0, Qt.AlignVCenter)

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
        self.nav_layout = QVBoxLayout(self.nav_frame)
        self.nav_layout.setContentsMargins(12, 12, 12, 12)
        self.nav_layout.setSpacing(8)
        content_layout.addWidget(self.nav_frame)

        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet(SCROLL_AREA_STYLE)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.scroll_content = QFrame()
        self.scroll_content.setStyleSheet("QFrame { background-color: #262626; border: none; }")
        self.scroll_area.setWidget(self.scroll_content)
        content_layout.addWidget(self.scroll_area)
        main_layout.addLayout(content_layout, 1)

        self.bottom_bar = QFrame()
        self.bottom_bar.setObjectName("bottomBar")
        self.bottom_bar.setStyleSheet(BOTTOM_BAR_STYLE)
        self.bottom_bar.setFixedHeight(60)
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(28, 12, 28, 12)
        bottom_layout.setSpacing(12)
        bottom_layout.addStretch()

        self.cancel_button = QPushButton(tr("common.cancel"))
        self.cancel_button.setMinimumWidth(80)
        self.cancel_button.clicked.connect(self.close)
        bottom_layout.addWidget(self.cancel_button)

        self.save_button = QPushButton(tr("common.save"))
        self.save_button.setObjectName("primaryButton")
        self.save_button.setMinimumWidth(80)
        self.save_button.clicked.connect(self.save_current_tab)
        bottom_layout.addWidget(self.save_button)

        main_layout.addWidget(self.bottom_bar)
        self.status_toast = AnimatedStatusToast(self.window_shell)

    def _register_tabs(self):
        self.tab_buttons = {}
        self.tab_widgets = {
            BasicSettingsTab.tab_name: BasicSettingsTab(),
            SmartConfigTab.tab_name: SmartConfigTab(),
            LifeManagementTab.tab_name: LifeManagementTab(
                is_enabled_getter=self._is_life_enabled,
                set_enabled_callback=self._set_life_enabled,
                reset_callback=self._reset_life,
                feedback_callback=self._set_feedback,
                is_dead_getter=self._is_life_dead,
                export_callback=self._export_life,
                import_callback=self._import_life,
            ),
            AboutTab.tab_name: AboutTab(),
        }

        tab_order = [BasicSettingsTab.tab_name, SmartConfigTab.tab_name, LifeManagementTab.tab_name, AboutTab.tab_name]

        # 若有已加载的 mod，则插入 Mod 信息标签页（位于"关于"之前）
        try:
            from module.life.runtime import get_mod_registry
            _reg = get_mod_registry()
            if _reg is not None and _reg.get_loaded_mod_ids():
                mod_tab = ModInfoTab()
                self.tab_widgets[ModInfoTab.tab_name] = mod_tab
                tab_order.insert(tab_order.index(AboutTab.tab_name), ModInfoTab.tab_name)
        except Exception as _e:
            _log.WARN(f"[Settings]注册 Mod 标签页失败: {_e}")

        if self.developer_mode:
            self.tab_widgets[DebugTab.tab_name] = DebugTab(
                throw_error_callback=self._throw_test_error,
                feedback_callback=self._set_feedback,
                duration_changed_callback=self._update_toast_duration,
                initial_duration_ms=self.toast_duration_ms,
                move_left_callback=self._trigger_move_left,
                move_right_callback=self._trigger_move_right,
                jump_callback=self._trigger_jump,
                hide_callback=self._trigger_hide,
                show_app_callback=self._trigger_show_app,
                open_life_debug_callback=self._open_life_debug_window,
            )
            tab_order.append(DebugTab.tab_name)

        for tab_name in tab_order:
            btn = QPushButton(tab_name)
            btn.setStyleSheet(NAV_BUTTON_STYLE)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked, name=tab_name: self.switch_tab(name))
            self.tab_buttons[tab_name] = btn
            self.nav_layout.addWidget(btn)

        self.nav_layout.addStretch()

        scroll_layout = QVBoxLayout(self.scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        for widget in self.tab_widgets.values():
            scroll_layout.addWidget(widget)
            widget.setVisible(False)
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

    def _init_mouse_feedback(self):
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

    def _is_in_resize_zone(self, local_pos):
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
            new_height = max(400, min(1200, self._resize_start_size.height() + delta.y()))

        self.resize(int(new_width), int(new_height))

    def _map_event_pos_to_self(self, watched, event):
        if not hasattr(event, "position"):
            return None
        return watched.mapTo(self, event.position().toPoint())

    def _apply_close_button_style(self):
        self.min_button.setStyleSheet(
            """
            QPushButton#minButton {
                background-color: transparent;
                border: 1px solid transparent;
                color: #dcdcdc;
                font-size: 16px;
                font-weight: 700;
                border-radius: 8px;
                padding: 0px;
            }
            QPushButton#minButton:hover {
                background-color: #3a3a3a;
                color: #ffffff;
            }
            QPushButton#minButton:pressed {
                background-color: #2e2e2e;
                color: #ffffff;
            }
            """
        )

        self.close_button.setStyleSheet(
            """
            QPushButton#closeButton {
                background-color: transparent;
                border: 1px solid transparent;
                color: #dcdcdc;
                font-size: 18px;
                font-weight: 600;
                border-radius: 8px;
                padding: 0px;
            }
            QPushButton#closeButton:hover {
                background-color: #f95f53;
                color: #ffffff;
            }
            QPushButton#closeButton:pressed {
                background-color: #d94a3f;
                color: #ffffff;
            }
            """
        )

        self.pin_button.setStyleSheet(
            """
            QPushButton#pinButton {
                background-color: transparent;
                border: 1px solid transparent;
                color: #dcdcdc;
                font-size: 15px;
                font-weight: 700;
                border-radius: 8px;
                padding: 0px;
            }
            QPushButton#pinButton:hover {
                background-color: #3a3a3a;
                color: #ffffff;
            }
            QPushButton#pinButton:checked {
                background-color: #1f5a9e;
                border: 1px solid #3f79c3;
                color: #ffffff;
            }
            """
        )

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

    def _init_scrollbar_fade(self):
        scrollbar = self.scroll_area.verticalScrollBar()
        self._scrollbar_opacity = QGraphicsOpacityEffect(scrollbar)
        scrollbar.setGraphicsEffect(self._scrollbar_opacity)

        self._scrollbar_anim = QPropertyAnimation(self._scrollbar_opacity, b"opacity", self)
        self._scrollbar_anim.setDuration(220)
        self._scrollbar_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._scrollbar_idle_timer = QTimer(self)
        self._scrollbar_idle_timer.setSingleShot(True)
        self._scrollbar_idle_timer.timeout.connect(self._fade_scrollbar)

        scrollbar.valueChanged.connect(self._show_scrollbar)
        scrollbar.rangeChanged.connect(lambda *_: self._show_scrollbar())
        self.scroll_area.viewport().installEventFilter(self)
        scrollbar.installEventFilter(self)

        self._show_scrollbar()

    def _set_feedback(self, message: str = "", level: str = "info"):
        if not message:
            self.status_toast.dismiss(animated=True)
            return

        self.status_toast.set_hide_duration(self.toast_duration_ms)
        self.status_toast.show_message(message, level, self.toast_duration_ms)

    def _update_toast_duration(self, seconds: int):
        self.toast_duration_ms = max(1000, int(seconds) * 1000)
        self.status_toast.set_hide_duration(self.toast_duration_ms)

    def _update_bottom_actions(self):
        current_widget = self.tab_widgets.get(self.active_tab)
        can_save = bool(getattr(current_widget, "can_save", False)) if current_widget else False
        self.save_button.setVisible(can_save)
        self.cancel_button.setText(tr("common.close") if not can_save else tr("common.cancel"))

    def _save_with_feedback(self, save_func):
        try:
            save_result = save_func()
        except ValueError as exc:
            self._set_feedback(str(exc), "error")
            return
        except Exception as exc:
            _log.ERROR(f"保存设置失败: {exc}")
            self._set_feedback(tr("settings.window.feedback.save_failed", error=exc), "error")
            return

        if isinstance(save_result, str) and save_result.strip():
            self._set_feedback(save_result, "success")
        else:
            self._set_feedback(tr("settings.window.feedback.saved"), "success")

    def save_current_tab(self):
        current_widget = self.tab_widgets.get(self.active_tab)
        if current_widget and getattr(current_widget, "can_save", False):
            save_func = getattr(current_widget, "save_tab", None)
            if callable(save_func):
                self._save_with_feedback(save_func)
                return
        self._set_feedback(tr("settings.window.feedback.no_save_content"), "info")

    def switch_tab(self, tab_name: str):
        for name, btn in self.tab_buttons.items():
            btn.setStyleSheet(NAV_BUTTON_ACTIVE_STYLE if name == tab_name else NAV_BUTTON_STYLE)

        for widget in self.tab_widgets.values():
            widget.setVisible(False)

        if tab_name in self.tab_widgets:
            self.tab_widgets[tab_name].setVisible(True)

        self.active_tab = tab_name

        # 切换到基础设置时刷新语言列表（mod 加载后可能新增语言）
        if tab_name == BasicSettingsTab.tab_name:
            tab_widget = self.tab_widgets.get(tab_name)
            if hasattr(tab_widget, "refresh_locale_combo"):
                tab_widget.refresh_locale_combo()

        self._set_feedback()
        self._update_bottom_actions()

    def _throw_test_error(self):
        try:
            raise RuntimeError("这是一个测试错误！系统异常处理应该捕获这个错误。")
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            sys.excepthook(exc_type, exc_value, exc_traceback)

    def _trigger_move_left(self, move_count: int):
        from Event.Ai.walk import auto_walk
        from Event.input.move import move_left
        from ui.PetWindow import PetWindow

        count = max(1, int(move_count))
        auto_walk.is_paused_due_to_action = True
        auto_walk.stop_timer()
        PetWindow.move_count = count
        move_left(PetWindow)
        self._set_feedback(tr("settings.window.debug.trigger_left", count=count), "success")

    def _trigger_move_right(self, move_count: int):
        from Event.Ai.walk import auto_walk
        from Event.input.move import move_right
        from ui.PetWindow import PetWindow

        count = max(1, int(move_count))
        auto_walk.is_paused_due_to_action = True
        auto_walk.stop_timer()
        PetWindow.move_count = count
        move_right(PetWindow)
        self._set_feedback(tr("settings.window.debug.trigger_right", count=count), "success")

    def _trigger_jump(self):
        from Event.Ai.walk import auto_walk
        from Event.input.move import move_jump
        from ui.PetWindow import PetWindow

        auto_walk.is_paused_due_to_action = True
        auto_walk.stop_timer()
        move_jump(PetWindow)
        self._set_feedback(tr("settings.window.debug.trigger_jump"), "success")

    def _trigger_hide(self):
        from Event.setting.system import HideApp
        from ui.PetWindow import PetWindow

        HideApp(PetWindow)
        self._set_feedback(tr("settings.window.debug.trigger_hide"), "success")

    def _trigger_show_app(self):
        from Event.setting.system import ShowApp
        from ui.PetWindow import PetWindow

        ShowApp(PetWindow)
        self._set_feedback(tr("settings.window.debug.trigger_show"), "success")

    def _open_life_debug_window(self):
        from ui.life import LifeDebugWindow

        existing = getattr(self, "life_debug_window", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

        self.life_debug_window = LifeDebugWindow(self)
        self.life_debug_window.show()
        self.life_debug_window.raise_()
        self.life_debug_window.activateWindow()
        self._set_feedback(tr("settings.window.debug.open_life_debug", "已打开养成调试窗口"), "success")

    def _is_life_enabled(self) -> bool:
        from module.life.runtime import is_life_loop_active
        return is_life_loop_active()

    def _is_life_dead(self) -> bool:
        from module.life.runtime import get_life_system
        return get_life_system().is_dead

    def _set_life_enabled(self, enabled: bool) -> None:
        from module.life.runtime import set_life_enabled
        set_life_enabled(enabled)

    def _reset_life(self) -> None:
        from module.life.runtime import get_life_system
        get_life_system().reset_profile()

    def _export_life(self, file_path: str) -> tuple[bool, str]:
        from module.life.runtime import get_life_system
        return get_life_system().export_profile(file_path)

    def _import_life(self, file_path: str) -> tuple[bool, str]:
        from module.life.runtime import get_life_system
        life = get_life_system()
        ok, err = life.import_profile(file_path)
        if ok:
            life.save("default")
        return ok, err

    def _open_life_window(self):
        from ui.life import LifeWindow

        existing = getattr(self, "life_window", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

        self.life_window = LifeWindow(self)
        self.life_window.show()
        self.life_window.raise_()
        self.life_window.activateWindow()
        self._set_feedback(tr("settings.window.debug.open_life", "已打开养成面板"), "success")

    def _list_life_buffs(self) -> list[str]:
        from module.life.runtime import get_life_system

        life = get_life_system()
        return life.list_buff_ids()

    def _list_life_effects(self) -> list[str]:
        from module.life.runtime import get_life_system

        life = get_life_system()
        return life.list_active_effect_ids()

    def _apply_life_effect(self, buff_id: str, duration_ticks: int):
        from module.life.runtime import get_life_system

        buff_id = str(buff_id).strip()
        if not buff_id:
            self._set_feedback(tr("settings.window.debug.life_effect.empty"), "error")
            return

        life = get_life_system()
        if life.apply_buff(buff_id, duration_override=max(1, int(duration_ticks))):
            self._set_feedback(
                tr("settings.window.debug.life_effect.applied", effect=f"{buff_id} ({int(duration_ticks)} tick)"),
                "success",
            )
            return
        self._set_feedback(tr("settings.window.debug.life_effect.apply_failed", effect=buff_id), "error")

    def _clear_life_effect(self, effect_id: str):
        from module.life.runtime import get_life_system

        effect_id = str(effect_id).strip()
        if not effect_id:
            self._set_feedback(tr("settings.window.debug.life_effect.empty"), "error")
            return

        life = get_life_system()
        if life.clear_effect(effect_id):
            self._set_feedback(tr("settings.window.debug.life_effect.cleared", effect=effect_id), "success")
            return
        self._set_feedback(tr("settings.window.debug.life_effect.clear_failed", effect=effect_id), "info")

    def _show_scrollbar(self):
        self._scrollbar_anim.stop()
        self._scrollbar_anim.setStartValue(self._scrollbar_opacity.opacity())
        self._scrollbar_anim.setEndValue(0.95)
        self._scrollbar_anim.start()
        self._scrollbar_idle_timer.start(1400)

    def _fade_scrollbar(self):
        self._scrollbar_anim.stop()
        self._scrollbar_anim.setStartValue(self._scrollbar_opacity.opacity())
        self._scrollbar_anim.setEndValue(0.25)
        self._scrollbar_anim.start()

    def eventFilter(self, watched, event):
        if watched in self._feedback_widgets or watched in self.tab_widgets.values():
            local_pos = self._map_event_pos_to_self(watched, event)
            resize_edge = self._get_resize_edge(local_pos) if local_pos is not None else None

            if event.type() == QEvent.MouseMove:
                if self._resizing:
                    self._apply_resize_from_edge(event.globalPosition().toPoint())
                    self.setCursor(QCursor(self._cursor_by_edge(self._resize_edge)))
                    return True

                if self._dragging:
                    current_global = event.globalPosition().toPoint()
                    delta = current_global - self._drag_start_pos
                    self.move(self.pos() + delta)
                    self._drag_start_pos = current_global
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

                if watched in (self.top_bar, self.title_label):
                    self._dragging = True
                    self._drag_start_pos = event.globalPosition().toPoint()
                    return True

            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._resizing = False
                self._resize_edge = None
                self._resize_start_pos = None
                self._resize_start_size = None
                self._dragging = False
                self._drag_start_pos = None
                self.setCursor(QCursor(self._cursor_by_edge(resize_edge)))

        if watched in (self.scroll_area.viewport(), self.scroll_area.verticalScrollBar()):
            if event.type() in (QEvent.Enter, QEvent.Wheel):
                self._show_scrollbar()
            elif event.type() == QEvent.Leave:
                self._scrollbar_idle_timer.start(800)

        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "status_toast"):
            self.status_toast.reposition()
