from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton, QFrame,
    QScrollArea, QGraphicsDropShadowEffect, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QEvent, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QParallelAnimationGroup, Property
from PySide6.QtGui import QColor, QCursor, QPainter
from typing import Optional
import sys

from ui.PetWindow import PetWindow
from ui.styles.toggle_switch import ToggleSwitch
from ui.styles.dialog_theme import apply_adobe_dialog_theme, apply_frameless_window_theme
from Event.Ai.walk import auto_walk
from Event.setting.system import AppStayTop
from util.log import _log
from util.version import APP_NAME, version, author, github_link

LABEL_WIDTH = 148
INPUT_WIDTH = 132
PROB_LABEL_WIDTH = LABEL_WIDTH
PROB_WIDTH = INPUT_WIDTH


class ScrollingLabel(QFrame):
    """支持文本平移滚动的标签（标签作为遮罩）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusToastLabel")
        self._max_content_width = 160
        self.setMaximumWidth(self._max_content_width)
        self.setMinimumWidth(1)
        self.setFixedWidth(1)
        self.setFixedHeight(16)
        self.setStyleSheet("QFrame#statusToastLabel { border: none; background: transparent; }")

        self._full_text = ""
        self._text_color = QColor("#ffffff")
        self._text_width = 0
        self._scroll_offset = 0
        self._scroll_range = 0
        self._edge_buffer_px = 0
        self._edge_pause_ms = 1000
        self._scroll_anim: Optional[QPropertyAnimation] = None
        self._reverse_anim: Optional[QPropertyAnimation] = None
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._start_scroll_animation)
        self._edge_pause_timer = QTimer(self)
        self._edge_pause_timer.setSingleShot(True)
        self._edge_pause_timer.timeout.connect(self._on_edge_pause_timeout)
        self._resume_reverse = False

    def set_max_content_width(self, width: int):
        self._max_content_width = max(32, int(width))
        self.setMaximumWidth(self._max_content_width)

    def set_text_color(self, color_hex: str):
        self._text_color = QColor(color_hex)
        self.update()

    def setText(self, text: str):
        """设置文本并检查是否需要滚动"""
        self._full_text = text
        self._text_width = self.fontMetrics().horizontalAdvance(self._full_text)
        target_width = min(self._max_content_width, max(1, self._text_width))
        self.setFixedWidth(target_width)
        self.stop_scroll()
        self._set_scroll_offset(0)

        # 先静态显示，再启动平移
        self._scroll_timer.start(450)

    def _start_scroll_animation(self):
        """当文本宽度超过容器时启动滚动动画"""
        if not self._full_text:
            return

        overflow = self._text_width - self.width()
        if overflow <= 0:
            self._set_scroll_offset(0)
            return

        self.stop_scroll()
        self._scroll_range = overflow + self._edge_buffer_px
        duration = max(2200, int(self._scroll_range * 24))

        self._scroll_anim = QPropertyAnimation(self, b"scrollOffset", self)
        self._scroll_anim.setStartValue(0)
        self._scroll_anim.setEndValue(-self._scroll_range)
        self._scroll_anim.setDuration(duration)
        self._scroll_anim.setEasingCurve(QEasingCurve.Linear)
        self._scroll_anim.finished.connect(self._schedule_reverse)
        self._scroll_anim.start()

    def _reverse_scroll(self):
        if self._scroll_range <= 0:
            self._set_scroll_offset(0)
            return

        self._reverse_anim = QPropertyAnimation(self, b"scrollOffset", self)
        self._reverse_anim.setStartValue(self._scroll_offset)
        self._reverse_anim.setEndValue(0)
        self._reverse_anim.setDuration(max(2200, int(self._scroll_range * 24)))
        self._reverse_anim.setEasingCurve(QEasingCurve.Linear)
        self._reverse_anim.finished.connect(self._schedule_forward)
        self._reverse_anim.start()

    def _schedule_reverse(self):
        self._resume_reverse = True
        self._edge_pause_timer.start(self._edge_pause_ms)

    def _schedule_forward(self):
        self._resume_reverse = False
        self._edge_pause_timer.start(self._edge_pause_ms)

    def _on_edge_pause_timeout(self):
        if self._resume_reverse:
            self._reverse_scroll()
        else:
            self._start_scroll_animation()

    def stop_scroll(self):
        self._scroll_timer.stop()
        self._edge_pause_timer.stop()
        if self._scroll_anim is not None:
            self._scroll_anim.stop()
            self._scroll_anim = None
        if self._reverse_anim is not None:
            self._reverse_anim.stop()
            self._reverse_anim = None

    def _get_scroll_offset(self):
        return self._scroll_offset

    def _set_scroll_offset(self, value):
        self._scroll_offset = int(value)
        self.update()

    scrollOffset = Property(int, _get_scroll_offset, _set_scroll_offset)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._full_text:
            return

        painter = QPainter(self)
        painter.setPen(self._text_color)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        metrics = self.fontMetrics()
        baseline = (self.height() + metrics.ascent() - metrics.descent()) // 2
        painter.drawText(self._scroll_offset, baseline, self._full_text)


class AnimatedStatusToast(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._visible_pos = QPoint()
        self._hidden_pos = QPoint()
        self._hide_duration_ms = 10000
        self._current_level = "success"

        self.setObjectName("statusToast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()
        self.setMaximumWidth(180)  # 减小到更紧凑的宽度

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)  # 减小内边距
        layout.setSpacing(0)

        self.message_label = ScrollingLabel()
        self.message_label.set_max_content_width(164)
        layout.addWidget(self.message_label)

        self.show_slide_anim = QPropertyAnimation(self, b"pos", self)
        self.show_slide_anim.setDuration(260)
        self.show_slide_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.hide_slide_anim = QPropertyAnimation(self, b"pos", self)
        self.hide_slide_anim.setDuration(200)
        self.hide_slide_anim.setEasingCurve(QEasingCurve.InCubic)
        self.hide_slide_anim.finished.connect(self._finish_hide)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.dismiss)

    def set_hide_duration(self, duration_ms: int):
        self._hide_duration_ms = max(500, int(duration_ms))

    def show_message(self, message: str, level: str = "success", duration_ms: Optional[int] = None):
        palette = {
            "success": ("#0f8a4a", "#ffffff"),
            "error": ("#b23c3c", "#ffffff"),
            "info": ("#1f5a9e", "#ffffff"),
        }
        background, foreground = palette.get(level, palette["info"])
        self._current_level = level

        self.hide_timer.stop()
        self.show_slide_anim.stop()
        self.hide_slide_anim.stop()
        
        # 停止之前的滚动动画
        self.message_label.stop_scroll()
        
        self.hide()

        self.message_label.setText(message)
        self.message_label.set_text_color(foreground)
        self.setStyleSheet(
            "QFrame#statusToast {"
            f"background-color: {background};"
            "border: none;"
            "border-radius: 6px;"
            "}"
            "QFrame#statusToastLabel {"
            "font-size: 10px;"
            "font-weight: 600;"
            "letter-spacing: 0.2px;"
            "}"
        )

        self.adjustSize()
        self._update_anchor_positions()
        self.move(self._hidden_pos)
        self.raise_()
        self.show()

        self.show_slide_anim.setStartValue(self._hidden_pos)
        self.show_slide_anim.setEndValue(self._visible_pos)
        self.show_slide_anim.start()

        self.hide_timer.start(duration_ms if duration_ms is not None else self._hide_duration_ms)

    def dismiss(self, animated: bool = True):
        if not self.isVisible():
            return

        self.hide_timer.stop()
        self.show_slide_anim.stop()
        
        # 停止滚动动画
        self.message_label.stop_scroll()

        if not animated:
            self.hide()
            return

        self._update_anchor_positions()
        self.hide_slide_anim.setStartValue(self.pos())
        self.hide_slide_anim.setEndValue(self._hidden_pos)
        self.hide_slide_anim.start()

    def reposition(self):
        self._update_anchor_positions()
        if self.isVisible():
            self.move(self._visible_pos)

    def _update_anchor_positions(self):
        parent = self.parentWidget()
        if parent is None:
            return

        margin_left = 12
        margin_bottom = 12
        self.adjustSize()
        w, h = self.width(), self.height()
        p_h = parent.height()
        
        # 确保 y 坐标不会为负，位置在底部
        visible_y = max(0, p_h - h - margin_bottom)
        self._visible_pos = QPoint(margin_left, visible_y)
        # 隐藏位置在可见位置下方 12px
        self._hidden_pos = QPoint(margin_left, visible_y + 12)

    def _finish_hide(self):
        self.hide()

class UnifiedSettingsWindow(QDialog):
    """统一的设置窗口，包含三个标签页：基础设置、智能配置、关于"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._resizing = False
        self._dragging = False
        self._resize_start_pos = None
        self._drag_start_pos = None
        self._resize_grip_size = 10
        self._feedback_widgets = []
        self.toast_duration_ms = 10000
        self.setWindowTitle("设置")
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setFixedSize(800, 600)
        self.setWindowFlags((self.windowFlags() & ~Qt.Tool) | Qt.Window | Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # 外层透明布局
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(0)
        
        # 窗口外壳
        self.window_shell = QFrame(self)
        self.window_shell.setObjectName("windowShell")
        self.window_shell.setAttribute(Qt.WA_StyledBackground, True)
        outer_layout.addWidget(self.window_shell)
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)  # 减小阴影模糊半径，从 60 改为 20
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 48))  # 减小阴影不透明度
        self.window_shell.setGraphicsEffect(shadow)
        self.window_shell.setStyleSheet(
            "QFrame#windowShell { background-color: #262626; border: 1px solid #3a3a3a; border-radius: 14px; }"
        )
        
        # 窗口内部布局
        main_layout = QVBoxLayout(self.window_shell)
        # 留出1px内边距，避免底栏背景覆盖外壳圆角
        main_layout.setContentsMargins(1, 1, 1, 1)
        main_layout.setSpacing(0)
        
        # 顶部栏（包含关闭按钮）
        self.top_bar = QFrame()
        self.top_bar.setStyleSheet("QFrame { background-color: transparent; border: none; }")
        self.top_bar.setFixedHeight(64)
        top_bar_layout = QHBoxLayout(self.top_bar)
        top_bar_layout.setContentsMargins(28, 12, 20, 12)
        top_bar_layout.setSpacing(0)
        
        self.title_label = QLabel("设置")
        self.title_label.setObjectName("title")
        top_bar_layout.addWidget(self.title_label, 0, Qt.AlignVCenter)
        top_bar_layout.addStretch()

        self.min_button = QPushButton("−")
        self.min_button.setObjectName("minButton")
        self.min_button.setFixedSize(44, 32)
        self.min_button.clicked.connect(self.showMinimized)
        top_bar_layout.addWidget(self.min_button, 0, Qt.AlignVCenter)
        
        # 右上角关闭按钮
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(44, 32)
        self.close_button.clicked.connect(self.close)
        top_bar_layout.addWidget(self.close_button, 0, Qt.AlignVCenter)
        
        main_layout.addWidget(self.top_bar)
        
        # 分割线
        divider = QFrame()
        divider.setStyleSheet("QFrame { background-color: #3a3a3a; border: none; }")
        divider.setFixedHeight(1)
        main_layout.addWidget(divider)
        
        # 主内容区域（左侧导航 + 右侧内容）
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # 左侧标签栏
        self.nav_frame = QFrame()
        self.nav_frame.setStyleSheet("QFrame { background-color: #1f1f1f; border: none; border-right: 1px solid #3a3a3a; }")
        self.nav_frame.setFixedWidth(180)
        nav_layout = QVBoxLayout(self.nav_frame)
        nav_layout.setContentsMargins(12, 12, 12, 12)
        nav_layout.setSpacing(8)
        
        # 标签页按钮
        self.tab_buttons = {}
        self.tab_widgets = {}
        
        # 创建导航按钮
        tab_names = ["基础设置", "智能配置", "关于", "调试"]
        self.active_tab = None
        
        for tab_name in tab_names:
            btn = QPushButton(tab_name)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: #a6a6a6;
                    padding: 10px 12px;
                    text-align: left;
                    border-radius: 6px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #3a3a3a;
                    color: #f5f5f5;
                }
                QPushButton:pressed {
                    background-color: #3a3a3a;
                }
            """)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked, name=tab_name: self.switch_tab(name))
            self.tab_buttons[tab_name] = btn
            nav_layout.addWidget(btn)
        
        nav_layout.addStretch()
        content_layout.addWidget(self.nav_frame)
        
        # 右侧可滚动内容区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #262626;
                border: none;
            }
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 0.04);
                width: 11px;
                border: none;
                border-radius: 5px;
                margin: 6px 2px 6px 2px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(245, 245, 245, 0.55);
                border-radius: 5px;
                min-height: 28px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(245, 245, 245, 0.8);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 滚动区域的内容容器
        self.scroll_content = QFrame()
        self.scroll_content.setStyleSheet("QFrame { background-color: #262626; border: none; }")
        self.scroll_area.setWidget(self.scroll_content)
        
        content_layout.addWidget(self.scroll_area)
        main_layout.addLayout(content_layout, 1)
        
        # 底部按钮栏
        self.bottom_bar = QFrame()
        self.bottom_bar.setObjectName("bottomBar")
        self.bottom_bar.setStyleSheet(
            "QFrame#bottomBar { background-color: #1f1f1f; border-top: 1px solid #3a3a3a; "
            "border-bottom-left-radius: 13px; border-bottom-right-radius: 13px; }"
        )
        self.bottom_bar.setFixedHeight(60)
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(28, 12, 28, 12)
        bottom_layout.setSpacing(12)
        bottom_layout.addStretch()
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setMinimumWidth(80)
        self.cancel_button.clicked.connect(self.close)
        bottom_layout.addWidget(self.cancel_button)
        
        self.save_button = QPushButton("保存")
        self.save_button.setObjectName("primaryButton")
        self.save_button.setMinimumWidth(80)
        self.save_button.clicked.connect(self.save_current_tab)
        bottom_layout.addWidget(self.save_button)
        
        main_layout.addWidget(self.bottom_bar)
        self.status_toast = AnimatedStatusToast(self.window_shell)
        
        # 创建标签页内容
        self._create_tab_contents()
        
        # 应用主题
        apply_adobe_dialog_theme(self)
        apply_frameless_window_theme(self)
        self._apply_close_button_style()
        self._init_scrollbar_fade()
        self._init_mouse_feedback()
        
        # 初始化显示第一个标签页
        self.switch_tab("基础设置")

    def _init_mouse_feedback(self):
        # 让拖动与边缘缩放在子控件区域也能触发
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
        return local_pos.y() >= self.height() - self._resize_grip_size

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
    
    def _create_tab_contents(self):
        """创建所有标签页的内容"""
        # 基础设置标签页
        self.tab_widgets["基础设置"] = self._create_settings_tab()
        
        # 智能配置标签页
        self.tab_widgets["智能配置"] = self._create_smartconfig_tab()
        
        # 关于标签页
        self.tab_widgets["关于"] = self._create_about_tab()
        
        # 调试标签页
        self.tab_widgets["调试"] = self._create_debug_tab()
        
        # 将所有标签页添加到滚动区域布局中，并全部隐藏
        scroll_layout = QVBoxLayout(self.scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        
        for widget_name, widget in self.tab_widgets.items():
            scroll_layout.addWidget(widget)
            widget.setVisible(False)  # 初始全部隐藏
            widget.setMouseTracking(True)
            widget.installEventFilter(self)
    
    def _create_settings_tab(self) -> QFrame:
        """创建基础设置标签页"""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(26)
        
        # 动作节奏卡片
        action_card = self._create_section_card("动作节奏", "调整宠物运动的频率")
        action_layout = action_card.layout()
        
        # 移动间隔
        move_layout = QHBoxLayout()
        move_layout.setSpacing(14)
        move_label = QLabel("移动动作间隔")
        move_label.setObjectName("fieldLabel")
        move_label.setFixedWidth(LABEL_WIDTH)
        move_layout.addWidget(move_label)
        self.timer_spin = QSpinBox()
        self.timer_spin.setRange(50, 10000)
        self.timer_spin.setValue(PetWindow.move_timer)
        self.timer_spin.setSuffix(" ms")
        self.timer_spin.setFixedWidth(INPUT_WIDTH)
        self.timer_spin.setAlignment(Qt.AlignRight)
        move_layout.addWidget(self.timer_spin)
        move_layout.addStretch()
        move_layout.setContentsMargins(0, 6, 0, 6)
        action_layout.addLayout(move_layout)
        
        # 待机动态间隔
        default_timer_layout = QHBoxLayout()
        default_timer_layout.setSpacing(14)
        default_timer_label = QLabel("待机动态间隔")
        default_timer_label.setObjectName("fieldLabel")
        default_timer_label.setFixedWidth(LABEL_WIDTH)
        default_timer_layout.addWidget(default_timer_label)
        self.default_timer_spin = QSpinBox()
        self.default_timer_spin.setRange(100, 5000)
        self.default_timer_spin.setValue(PetWindow.default_action_interval)
        self.default_timer_spin.setSuffix(" ms")
        self.default_timer_spin.setFixedWidth(INPUT_WIDTH)
        self.default_timer_spin.setAlignment(Qt.AlignRight)
        default_timer_layout.addWidget(self.default_timer_spin)
        default_timer_layout.addStretch()
        default_timer_layout.setContentsMargins(0, 6, 0, 6)
        action_layout.addLayout(default_timer_layout)
        
        layout.addWidget(action_card)
        layout.addSpacing(8)
        
        # 显示行为卡片
        display_card = self._create_section_card("显示行为", "控制宠物窗口的显示方式")
        display_layout = display_card.layout()
        
        # 窗口置顶
        top_layout = QHBoxLayout()
        top_layout.setSpacing(14)
        top_label = QLabel("窗口置顶")
        top_label.setObjectName("fieldLabel")
        top_label.setFixedWidth(LABEL_WIDTH)
        top_layout.addWidget(top_label)
        top_layout.addStretch()
        self.stay_top_check = ToggleSwitch()
        self.stay_top_check.setChecked(bool(PetWindow.windowFlags() & Qt.WindowStaysOnTopHint))
        top_layout.addWidget(self.stay_top_check)
        top_layout.setContentsMargins(0, 6, 0, 6)
        display_layout.addLayout(top_layout)
        
        # 待机动作
        action_layout_field = QHBoxLayout()
        action_layout_field.setSpacing(14)
        action_label = QLabel("待机动作")
        action_label.setObjectName("fieldLabel")
        action_label.setFixedWidth(LABEL_WIDTH)
        action_layout_field.addWidget(action_label)
        action_layout_field.addStretch()
        self.default_action_check = ToggleSwitch()
        self.default_action_check.setChecked(PetWindow.default_action)
        action_layout_field.addWidget(self.default_action_check)
        action_layout_field.setContentsMargins(0, 6, 0, 6)
        display_layout.addLayout(action_layout_field)
        
        layout.addWidget(display_card)
        layout.addStretch()
        
        return frame
    
    def _create_smartconfig_tab(self) -> QFrame:
        """创建智能配置标签页"""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(26)
        
        # 基础参数卡片
        base_card = self._create_section_card("基础参数", "控制智能运动触发时机与可移动范围")
        base_layout = base_card.layout()
        
        # 范围控制
        range_layout = QHBoxLayout()
        range_layout.setSpacing(14)
        range_label = QLabel("范围控制")
        range_label.setObjectName("fieldLabel")
        range_label.setFixedWidth(LABEL_WIDTH)
        range_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        range_layout.addWidget(range_label)
        self.range_spin = QSpinBox()
        self.range_spin.setRange(1, 8192)
        self.range_spin.setValue(PetWindow.max_move_range)
        self.range_spin.setSuffix(" px")
        self.range_spin.setFixedWidth(INPUT_WIDTH)
        self.range_spin.setAlignment(Qt.AlignRight)
        range_layout.addWidget(self.range_spin)
        range_layout.addStretch()
        range_layout.setContentsMargins(0, 6, 0, 6)
        base_layout.addLayout(range_layout)
        
        # 检查间隔
        check_layout = QHBoxLayout()
        check_layout.setSpacing(14)
        check_label = QLabel("检查间隔")
        check_label.setObjectName("fieldLabel")
        check_label.setFixedWidth(LABEL_WIDTH)
        check_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        check_layout.addWidget(check_label)
        self.check_spin = QSpinBox()
        self.check_spin.setRange(50, 1000)
        self.check_spin.setValue(auto_walk.check_time)
        self.check_spin.setSuffix(" ms")
        self.check_spin.setFixedWidth(INPUT_WIDTH)
        self.check_spin.setAlignment(Qt.AlignRight)
        check_layout.addWidget(self.check_spin)
        check_layout.addStretch()
        check_layout.setContentsMargins(0, 6, 0, 6)
        base_layout.addLayout(check_layout)
        
        # 空闲阈值
        idle_layout = QHBoxLayout()
        idle_layout.setSpacing(14)
        idle_label = QLabel("空闲阈值")
        idle_label.setObjectName("fieldLabel")
        idle_label.setFixedWidth(LABEL_WIDTH)
        idle_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        idle_layout.addWidget(idle_label)
        self.idle_spin = QSpinBox()
        self.idle_spin.setRange(1, 300)
        self.idle_spin.setValue(auto_walk.idle_threshold)
        self.idle_spin.setSuffix(" s")
        self.idle_spin.setFixedWidth(INPUT_WIDTH)
        self.idle_spin.setAlignment(Qt.AlignRight)
        idle_layout.addWidget(self.idle_spin)
        idle_layout.addStretch()
        idle_layout.setContentsMargins(0, 6, 0, 6)
        base_layout.addLayout(idle_layout)
        
        layout.addWidget(base_card)
        layout.addSpacing(8)
        
        # 动作权重卡片
        prob_card = self._create_section_card("动作权重", "三个几率总和不能超过 100%")
        prob_layout = prob_card.layout()
        
        prob_layout.addLayout(self._create_weight_row("左移", "left_spin", auto_walk._walk_left_per))
        prob_layout.addLayout(self._create_weight_row("右移", "right_spin", auto_walk._walk_right_per))
        prob_layout.addLayout(self._create_weight_row("跳跃", "jump_spin", auto_walk._jump_per))
        
        layout.addWidget(prob_card)
        layout.addSpacing(8)
        
        # 开关卡片
        switch_card = self._create_section_card("开关", "关闭后仅保留手动交互")
        switch_layout = switch_card.layout()
        
        automove_layout = QHBoxLayout()
        automove_layout.setSpacing(14)
        automove_label = QLabel("启用智能运动")
        automove_label.setObjectName("fieldLabel")
        automove_label.setFixedWidth(LABEL_WIDTH)
        automove_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        automove_layout.addWidget(automove_label)
        automove_layout.addStretch()
        self.automove_check = ToggleSwitch()
        self.automove_check.setChecked(PetWindow.AutoMove)
        automove_layout.addWidget(self.automove_check)
        automove_layout.setContentsMargins(0, 6, 0, 6)
        switch_layout.addLayout(automove_layout)
        
        layout.addWidget(switch_card)
        layout.addSpacing(6)
        
        hint_label = QLabel("提示: 概率总和超过 100% 时无法保存。")
        hint_label.setObjectName("helperText")
        layout.addWidget(hint_label)
        
        layout.addStretch()
        
        return frame
    
    def _create_about_tab(self) -> QFrame:
        """创建关于标签页"""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(26)

        app_card = self._create_section_card("应用信息", "版本与作者信息")
        app_info_layout = app_card.layout()

        name_row = QHBoxLayout()
        name_row.setSpacing(14)
        name_label = QLabel("应用名称")
        name_label.setObjectName("fieldLabel")
        name_label.setFixedWidth(LABEL_WIDTH)
        name_row.addWidget(name_label)
        name_value = QLabel(APP_NAME)
        name_value.setObjectName("subtitle")
        name_row.addWidget(name_value)
        name_row.addStretch()
        name_row.setContentsMargins(0, 6, 0, 6)
        app_info_layout.addLayout(name_row)

        version_row = QHBoxLayout()
        version_row.setSpacing(14)
        version_label = QLabel("当前版本")
        version_label.setObjectName("fieldLabel")
        version_label.setFixedWidth(LABEL_WIDTH)
        version_row.addWidget(version_label)
        version_value = QLabel(f"v{version}")
        version_value.setObjectName("subtitle")
        version_row.addWidget(version_value)
        version_row.addStretch()
        version_row.setContentsMargins(0, 6, 0, 6)
        app_info_layout.addLayout(version_row)

        author_row = QHBoxLayout()
        author_row.setSpacing(14)
        author_label = QLabel("开发者")
        author_label.setObjectName("fieldLabel")
        author_label.setFixedWidth(LABEL_WIDTH)
        author_row.addWidget(author_label)
        author_value = QLabel(author)
        author_value.setObjectName("subtitle")
        author_row.addWidget(author_value)
        author_row.addStretch()
        author_row.setContentsMargins(0, 6, 0, 6)
        app_info_layout.addLayout(author_row)

        layout.addWidget(app_card)
        layout.addSpacing(8)

        project_card = self._create_section_card("项目链接", "点击可在浏览器中打开仓库")
        project_layout = project_card.layout()

        link_label = QLabel(f"<a href='{github_link}'>GitHub: {github_link}</a>")
        link_label.setObjectName("fieldLabel")
        link_label.setOpenExternalLinks(True)
        project_layout.addWidget(link_label)

        desc_label = QLabel("一个可爱的桌面宠物应用")
        desc_label.setObjectName("helperText")
        project_layout.addWidget(desc_label)

        layout.addWidget(project_card)
        
        layout.addStretch()
        
        return frame
    
    def _create_debug_tab(self) -> QFrame:
        """创建调试标签页"""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(26)

        debug_card = self._create_section_card("调试工具", "用于手动验证异常处理流程")
        debug_layout = debug_card.layout()

        warn_label = QLabel("该操作会主动抛出一个测试异常，请仅在调试时使用。")
        warn_label.setObjectName("helperText")
        debug_layout.addWidget(warn_label)

        action_row = QHBoxLayout()
        action_row.setSpacing(14)
        action_label = QLabel("异常测试")
        action_label.setObjectName("fieldLabel")
        action_label.setFixedWidth(LABEL_WIDTH)
        action_row.addWidget(action_label)
        error_button = QPushButton("抛出测试错误")
        error_button.setObjectName("primaryButton")
        error_button.setMinimumWidth(160)
        error_button.clicked.connect(self._throw_test_error)
        action_row.addWidget(error_button)
        action_row.addStretch()
        debug_layout.addLayout(action_row)

        toast_card = self._create_section_card("提示动画", "用于预览保存成功/失败提示，并调整停留时长")
        toast_layout = toast_card.layout()

        duration_row = QHBoxLayout()
        duration_row.setSpacing(14)
        duration_label = QLabel("提示停留时长")
        duration_label.setObjectName("fieldLabel")
        duration_label.setFixedWidth(LABEL_WIDTH)
        duration_row.addWidget(duration_label)
        self.toast_duration_spin = QSpinBox()
        self.toast_duration_spin.setRange(1, 60)
        self.toast_duration_spin.setValue(self.toast_duration_ms // 1000)
        self.toast_duration_spin.setSuffix(" s")
        self.toast_duration_spin.setFixedWidth(INPUT_WIDTH)
        self.toast_duration_spin.setAlignment(Qt.AlignRight)
        self.toast_duration_spin.valueChanged.connect(self._update_toast_duration)
        duration_row.addWidget(self.toast_duration_spin)
        duration_row.addStretch()
        toast_layout.addLayout(duration_row)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(12)
        preview_label = QLabel("动画预览")
        preview_label.setObjectName("fieldLabel")
        preview_label.setFixedWidth(LABEL_WIDTH)
        preview_row.addWidget(preview_label)

        preview_success_button = QPushButton("成功提示")
        preview_success_button.clicked.connect(lambda: self._set_feedback("已保存", "success"))
        preview_row.addWidget(preview_success_button)

        preview_error_button = QPushButton("失败提示")
        preview_error_button.clicked.connect(
            lambda: self._set_feedback("保存失败：这是一个调试提示", "error")
        )
        preview_row.addWidget(preview_error_button)
        preview_row.addStretch()
        toast_layout.addLayout(preview_row)

        layout.addWidget(toast_card)

        layout.addWidget(debug_card)

        info_card = self._create_section_card("说明", "触发后应弹出全局错误窗口")
        info_layout = info_card.layout()
        info_text = QLabel("如果未出现错误弹窗，请检查 exception_hook 是否仍在 main.py 中正确注册。")
        info_text.setObjectName("helperText")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        layout.addWidget(info_card)
        
        layout.addStretch()
        
        return frame
    
    def _create_section_card(self, title: str, hint: str) -> QFrame:
        """创建卡片式段落"""
        card = QFrame()
        card.setObjectName("sectionCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(14)
        
        section_title = QLabel(title)
        section_title.setObjectName("sectionTitle")
        card_layout.addWidget(section_title)
        
        section_hint = QLabel(hint)
        section_hint.setObjectName("sectionHint")
        card_layout.addWidget(section_hint)
        
        return card
    
    def _create_weight_row(self, label_text: str, spin_attr_name: str, value: int) -> QHBoxLayout:
        """创建权重行（标签+数值框）"""
        row_layout = QHBoxLayout()
        row_layout.setSpacing(16)
        
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(PROB_LABEL_WIDTH)
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        row_layout.addWidget(label)
        
        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(value)
        spin.setSuffix(" %")
        spin.setFixedWidth(PROB_WIDTH)
        spin.setAlignment(Qt.AlignRight)
        row_layout.addWidget(spin)
        row_layout.addStretch()
        row_layout.setContentsMargins(0, 6, 0, 6)
        
        setattr(self, spin_attr_name, spin)
        return row_layout

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
        save_enabled_tabs = {"基础设置", "智能配置"}
        can_save = self.active_tab in save_enabled_tabs
        self.save_button.setVisible(can_save)
        self.cancel_button.setText("关闭" if not can_save else "取消")

    def _validate_smart_settings(self):
        total_per = self.left_spin.value() + self.right_spin.value() + self.jump_spin.value()
        if total_per > 100:
            raise ValueError(f"保存失败：动作权重总和不能超过 100%，当前为 {total_per}%")

    def _save_with_feedback(self, save_func):
        try:
            save_func()
        except ValueError as exc:
            self._set_feedback(str(exc), "error")
            return
        except Exception as exc:
            _log.ERROR(f"保存设置失败: {exc}")
            self._set_feedback(f"保存失败：{exc}", "error")
            return

        self._set_feedback("已保存", "success")

    def _save_basic_settings(self):
        PetWindow.move_timer = self.timer_spin.value()
        PetWindow.set_default_action_interval(self.default_timer_spin.value())
        AppStayTop(PetWindow, self.stay_top_check)
        PetWindow.set_default_action_enabled(self.default_action_check.isChecked())

        _log.INFO(
            f"基础设置已保存: 移动动作间隔={PetWindow.move_timer}ms, "
            f"待机动态间隔={PetWindow.default_action_interval}ms, "
            f"置顶={self.stay_top_check.isChecked()}, 待机动作={PetWindow.default_action}"
        )

    def _save_smart_settings(self):
        self._validate_smart_settings()

        PetWindow.max_move_range = self.range_spin.value()
        auto_walk.check_time = self.check_spin.value()
        auto_walk.idle_threshold = self.idle_spin.value()
        auto_walk._walk_left_per = self.left_spin.value()
        auto_walk._walk_right_per = self.right_spin.value()
        auto_walk._jump_per = self.jump_spin.value()
        PetWindow.AutoMove = self.automove_check.isChecked()
        auto_walk.start_timer()

        _log.INFO(
            f"智能配置已保存: 范围={PetWindow.max_move_range}, 检查间隔={auto_walk.check_time}ms, "
            f"空闲阈值={auto_walk.idle_threshold}s, 权重(左/右/跳)="
            f"{auto_walk._walk_left_per}/{auto_walk._walk_right_per}/{auto_walk._jump_per}, "
            f"AutoMove={PetWindow.AutoMove}"
        )

    def save_current_tab(self):
        if self.active_tab == "基础设置":
            self._save_with_feedback(self._save_basic_settings)
            return
        if self.active_tab == "智能配置":
            self._save_with_feedback(self._save_smart_settings)
            return
        self._set_feedback("当前标签页没有可保存的内容", "info")
    
    def switch_tab(self, tab_name: str):
        """切换标签页"""
        # 更新导航按钮样式
        for name, btn in self.tab_buttons.items():
            if name == tab_name:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f95f53;
                        border: none;
                        color: #ffffff;
                        padding: 10px 12px;
                        text-align: left;
                        border-radius: 6px;
                        font-size: 13px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #f95f53;
                        color: #ffffff;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        color: #a6a6a6;
                        padding: 10px 12px;
                        text-align: left;
                        border-radius: 6px;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #3a3a3a;
                        color: #f5f5f5;
                    }
                    QPushButton:pressed {
                        background-color: #3a3a3a;
                    }
                """)
        
        # 隐藏所有标签页内容
        for widget_name, widget in self.tab_widgets.items():
            widget.setVisible(False)
        
        # 显示选定的标签页内容
        if tab_name in self.tab_widgets:
            self.tab_widgets[tab_name].setVisible(True)
        
        self.active_tab = tab_name
        self._set_feedback()
        self._update_bottom_actions()
    
    def _throw_test_error(self):
        """抛出测试错误"""
        try:
            raise RuntimeError("这是一个测试错误！系统异常处理应该捕获这个错误。")
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            sys.excepthook(exc_type, exc_value, exc_traceback)

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
        feedback_widgets = getattr(self, "_feedback_widgets", [])
        tab_widgets = getattr(self, "tab_widgets", {})

        if watched in feedback_widgets or watched in tab_widgets.values():
            local_pos = self._map_event_pos_to_self(watched, event)
            in_resize_zone = local_pos is not None and self._is_in_resize_zone(local_pos)

            if event.type() == QEvent.MouseMove:
                if self._resizing and self._resize_start_pos is not None:
                    delta = event.globalPosition().y() - self._resize_start_pos
                    new_height = max(400, min(self.height() + delta, 1200))
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

                if in_resize_zone:
                    self.setCursor(QCursor(Qt.SizeVerCursor))
                else:
                    self.setCursor(QCursor(Qt.ArrowCursor))

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
                if in_resize_zone:
                    self.setCursor(QCursor(Qt.SizeVerCursor))
                else:
                    self.setCursor(QCursor(Qt.ArrowCursor))

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
    
