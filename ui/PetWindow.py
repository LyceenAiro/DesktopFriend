from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtGui import Qt, QMovie
from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt as QtC

import sys
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from ui.PetArt import *
from ui.BuffStatusBar import BuffStatusBar
from resources.image_resources import get_resource_pack_name

from util.log import _log
from util.version import version
from util.cfg import init_config_dir, load_config
from typing import Optional, List, Dict, Any

# 所有Event类型请通过注册表注册使用

class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()
        _log.INFO("初始化桌宠...")

        # 初始化配置文件夹和加载配置
        init_config_dir()
        basic_config = load_config("basic")
        smart_config = load_config("smart")

        self.setWindowTitle('')
        # 清除窗口框体和任务栏图标
        self.setWindowFlag(Qt.FramelessWindowHint | self.windowFlags() | QtC.Tool)
        # 默认设置在顶层
        if basic_config.get("stay_top", True):
            self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 宠物 128px + 4px 间隔 + 32px 图标列 = 164px
        self.setFixedSize(164, 128)

        self.mouse_press_position = None
        self.is_follow_mouse = False

        # AI逻辑：从配置文件加载
        self.AutoMove = smart_config.get("auto_move", True)
        self.auto_walk_on_show = True  # 隐藏/显示时的独立开关
        self.default_action = basic_config.get("default_action", True)
        self.default_action_interval = basic_config.get("default_action_interval", 600)

        # 行动点数
        self.move_count = 0
        self.move_timer = basic_config.get("move_timer", 200)

        # 原点位置（每次pickup结束后重置）
        self.origin_x = 0
        self.max_move_range = smart_config.get("max_move_range", 20)

        # 图像初始化
        self.PetArt = QLabel(self)
        self.PetArt.setPixmap(PetArtList[DEFAULT])
        self.PetArt.move(0, 0)
        
        # Buff 状态栏初始化（竖向三槽，紧贴宠物右边缘 128px 处）
        self.buff_status_bar = BuffStatusBar(self)
        self.buff_status_bar.move(128, 12)
        self.buff_status_bar.raise_()  # 确保在最上层

        # 最大x坐标
        self.screen_max_x = self.ScreenMaxX()

        # 定时器
        self.Picktimer = QTimer(self)
        self.Picktimer.setSingleShot(True)

        # 待机动画：在无动作时于 DEFAULT / DEFAULT2 间切换
        self.default_action_timer = QTimer(self)
        self.default_action_timer.timeout.connect(self._on_default_action_timer)
        self.default_action_timer.start(self.default_action_interval)
        self._default_action_toggle = False

        _log.INFO(f"初始化完成")
        _log.INFO(f"当前版本: v{version}")
        _log.INFO(f"作者: LyceenAiro")
        _log.INFO(f"开源链接: github.com/LyceenAiro/DesktopFriend")
        _log.INFO(f"资源包名：{get_resource_pack_name()}")
        _log.INFO(f"如果发现有任何问题均可在GitHub上提交issue或直接联系我")
        _log.INFO(f"该软件完全开源免费，禁止任何形式对此分支商用！")

        # 初始化动作系统
        self._init_action_system()

    def _init_action_system(self):
        """初始化 ActionSystem（延迟初始化以避免循环导入）。"""
        from module.default.action import ActionSystem
        from module.default.vanilla import register_vanilla_actions
        from ui.PetArt import PetArtList

        self.action_system = ActionSystem(
            self,
            default_interval_ms=self.default_action_interval,
        )
        register_vanilla_actions(self.action_system, PetArtList)
        from pathlib import Path
        action_dir = Path(__file__).resolve().parent.parent / "module" / "default" / "action"
        n = self.action_system.scan_action_directory(str(action_dir), source="builtin")
        _log.INFO(f"[Action]动作系统已初始化，已注册 {len(self.action_system.action_registry)} 个原版动作，从目录加载 {n} 个")

    # 屏幕最大X轴坐标
    def ScreenMaxX(self): return app.primaryScreen().size().width()

    def set_default_action_enabled(self, enabled: bool):
        self.default_action = bool(enabled)
        if not self.default_action:
            self._default_action_toggle = False
            self.stop_default_action_timer()
            self.PetArt.setPixmap(PetArtList[DEFAULT])
        else:
            self.start_default_action_timer()

    def stop_default_action_timer(self):
        if self.default_action_timer.isActive():
            self.default_action_timer.stop()

    def start_default_action_timer(self):
        if self.default_action and not self.default_action_timer.isActive():
            self.default_action_timer.start(self.default_action_interval)

    def set_default_action_interval(self, interval_ms: int):
        self.default_action_interval = int(interval_ms)
        if self.default_action_timer.isActive():
            self.default_action_timer.start(self.default_action_interval)

    def _is_idle_for_default_action(self) -> bool:
        if not self.isVisible() or not self.default_action:
            return False
        if self.is_follow_mouse:
            return False
        if self.move_count > 0:
            return False
        if hasattr(self, 'jump_timer') and self.jump_timer and self.jump_timer.isActive():
            return False
        if self.PetArt.movie() is not None and self.PetArt.movie().state() == QMovie.Running:
            return False
        # 检查动作系统：若有独占/序列动作播放，暂停待机动画
        if hasattr(self, 'action_system') and self.action_system is not None:
            if not self.action_system._vanilla_idle_active:
                return False
            if self.action_system._active_exclusive is not None:
                return False
        try:
            from Event.input.move import _walk
            if _walk.timer.isActive():
                return False
        except Exception:
            return False
        return True

    def _on_default_action_timer(self):
        if not self._is_idle_for_default_action():
            return
        self._default_action_toggle = not self._default_action_toggle
        self.PetArt.setPixmap(PetArtList[DEFAULT2] if self._default_action_toggle else PetArtList[DEFAULT])
    
    # 定时器注册
    def RegisterTimeout(self, callback): self.Picktimer.timeout.connect(callback)
    
    # ═══════════════════════════════════════
    # Buff 状态栏相关方法
    # ═══════════════════════════════════════
    
    def set_status_buffs(self, buffs: List[Dict[str, Any]]):
        """
        设置要显示在状态栏的 buff 列表
        
        Args:
            buffs: buff 数据字典列表（最多三个会被显示）
        """
        self.buff_status_bar.set_buffs(buffs)
    
    def clear_status_buffs(self):
        """清除所有状态栏 buff 显示"""
        self.buff_status_bar.clear_buffs()
    
    def update_status_buff_at(self, index: int, buff_data: Optional[Dict[str, Any]]):
        """
        更新特定位置的状态栏 buff
        
        Args:
            index: buff 位置（0-2）
            buff_data: buff 数据字典，或 None 清除
        """
        self.buff_status_bar.update_buff_at(index, buff_data)
    
    def get_displayed_status_buffs(self) -> List[Optional[Dict[str, Any]]]:
        """获取当前显示的状态栏 buff 列表"""
        return self.buff_status_bar.get_displayed_buffs()

    # 定时器注册

    # 菜单界面和功能注册
    def RegisterMenu(self, callback): self.menu_init = callback
    def RegisterTray(self, callback): self.tray_init = callback
    # 菜单事件注册
    def RegistercontextMenuEvent(self, callback): self.context_Menu_callback = callback
    def contextMenuEvent(self, event): self.context_Menu_callback(self, event)

    ##
    ##  指针事件初始化
    ##
    ##  事件注册
    def RegistermouseDoubleClickEvent(self, callback): self.double_click_callback = callback
    def RegistermousePressEvent(self, callback): self.mouse_Press_callback = callback
    def RegistermouseReleaseEvent(self, callback): self.mouse_Release_callback = callback
    def RegistermouseMoveEvent(self, callback): self.mouse_Move_callback = callback
    def RegisterenterEvent(self, callback): self.enter_callback = callback
    ##  注册绑定
    def mouseDoubleClickEvent(self, event): self.double_click_callback(self, event)
    def mousePressEvent(self, event): self.mouse_Press_callback(self, event)
    def mouseReleaseEvent(self, event): self.mouse_Release_callback(self, event)
    def mouseMoveEvent(self, event): self.mouse_Move_callback(self, event)
    def enterEvent(self, event): self.enter_callback(self, event)

PetWindow = DesktopPet()