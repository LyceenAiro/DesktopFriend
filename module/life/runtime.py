from __future__ import annotations

from PySide6.QtCore import QTimer

from module.life.main import LifeSystem
from resources.image_resources import get_resource_pack_display_name, get_resource_pack_name
from util.cfg import load_config
from util.log import _log

_life_system: LifeSystem | None = None
_life_timer: QTimer | None = None


def get_life_system() -> LifeSystem:
    global _life_system
    if _life_system is None:
        _life_system = LifeSystem()
        _life_system.character_name = get_resource_pack_display_name(get_resource_pack_name())
        _life_system.load("default")
        life_cfg = load_config("life")
        _life_system.paused = not bool(life_cfg.get("life_enabled", True))
    return _life_system


def is_life_loop_active() -> bool:
    """返回 tick 定时器当前是否运行中（不考虑 paused 标志）。"""
    return _life_timer is not None and _life_timer.isActive()


def set_life_enabled(enabled: bool) -> None:
    """启用或暂停养成系统（同步更新 LifeSystem.paused 与定时器状态）。"""
    life = get_life_system()
    life.paused = not enabled
    if enabled:
        if _life_timer is not None and not _life_timer.isActive():
            _life_timer.start()
            _log.INFO("[Life]养成系统已恢复")
    else:
        if _life_timer is not None and _life_timer.isActive():
            _life_timer.stop()
            _log.INFO("[Life]养成系统已暂停")


def start_life_loop(parent=None, interval_ms: int = 1000) -> QTimer:
    global _life_timer

    life = get_life_system()
    if _life_timer is None:
        _life_timer = QTimer(parent)

        def _on_tick():
            try:
                life.tick()
                life.save("default")
            except Exception as exc:
                _log.ERROR(f"[Life]tick失败: {exc}")

        _life_timer.timeout.connect(_on_tick)

    if interval_ms > 0:
        _life_timer.setInterval(int(interval_ms))
    if not _life_timer.isActive():
        _life_timer.start()
        _log.INFO(f"[Life]tick定时器已启动: {int(interval_ms)}ms")

    return _life_timer
