from __future__ import annotations

from PySide6.QtCore import QTimer

from module.life.main import LifeSystem
from resources.image_resources import get_resource_pack_display_name, get_resource_pack_name
from util.cfg import load_config
from util.log import _log

_life_system: LifeSystem | None = None
_life_timer: QTimer | None = None
_life_revive_timer: QTimer | None = None  # 桌宠死亡后的轻量检测计时器
_mod_registry = None  # type: ignore


def get_life_system() -> LifeSystem:
    global _life_system
    if _life_system is None:
        _log.INFO("[Life]初始化 LifeSystem 单例")
        _life_system = LifeSystem()
        _life_system.character_name = get_resource_pack_display_name(get_resource_pack_name())
        loaded = _life_system.load("default")
        life_cfg = load_config("life")
        _life_system.paused = not bool(life_cfg.get("life_enabled", True))
        _log.INFO(
            f"[Life]LifeSystem 已就绪 character={_life_system.character_name or '<unknown>'} "
            f"loaded={loaded} paused={_life_system.paused}"
        )
    return _life_system


def load_mods() -> dict:
    """扫描并加载 mod/ 目录下所有 mod，返回 execute_with_builtin_loader 结果。"""
    global _mod_registry
    from expansion.life.mod import LifeModRegistry

    life = get_life_system()
    _mod_registry = LifeModRegistry(mod_root="mod", protocol_version="0.3")
    result = _mod_registry.execute_with_builtin_loader(
        event_log_path="log/mod_event.log",
        life_system=life,
    )
    loaded = result.get("loaded", [])
    issues = result.get("issues", {})
    if loaded:
        _log.INFO(f"[Mod]已加载 {len(loaded)} 个 mod: {loaded}")
    elif not issues:
        _log.INFO("[Mod]未发现任何 mod")
    if issues:
        for mid, errs in issues.items():
            _log.WARN(f"[Mod]加载问题 {mid}: {errs}")
    return result


def get_mod_registry():
    return _mod_registry


def is_life_loop_active() -> bool:
    """返回 tick 定时器当前是否运行中（不考虑 paused 标志）。"""
    return _life_timer is not None and _life_timer.isActive()


def set_life_enabled(enabled: bool) -> None:
    """启用或暂停养成系统（同步更新 LifeSystem.paused 与定时器状态）。"""
    life = get_life_system()
    _log.INFO(f"[Life]请求切换养成系统 enabled={enabled}")
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
    global _life_timer, _life_revive_timer

    life = get_life_system()
    if _life_timer is None:
        _life_timer = QTimer(parent)
        _log.DEBUG("[Life]创建主 tick 定时器")

        def _on_tick():
            try:
                was_dead = life.is_dead
                life.tick()
                life.save("default")
                # 如果此 tick 导致死亡，切换到轻量复活检测计时器
                if not was_dead and life.is_dead:
                    _switch_to_revive_timer(parent)
            except Exception as exc:
                _log.EXCEPTION("[Life]tick失败", exc)

        _life_timer.timeout.connect(_on_tick)

    if interval_ms > 0:
        _life_timer.setInterval(int(interval_ms))
    if not _life_timer.isActive():
        _life_timer.start()
        _log.INFO(f"[Life]tick定时器已启动: {int(interval_ms)}ms")

    # 如果加载存档后已处于死亡状态，直接切换到轻量复活检测计时器
    if life.is_dead:
        _switch_to_revive_timer(parent)

    return _life_timer


def _switch_to_revive_timer(parent=None) -> None:
    """停止主 tick 计时器，启动轻量死亡检测计时器（每 5 秒检测一次是否可复活）。"""
    global _life_timer, _life_revive_timer

    if _life_timer is not None and _life_timer.isActive():
        _life_timer.stop()
    _log.INFO("[Life]桌宠死亡，切换到轻量检测计时器")

    if _life_revive_timer is None:
        _life_revive_timer = QTimer(parent)
        _log.DEBUG("[Life]创建轻量复活检测计时器")

        def _check_revive():
            life = get_life_system()
            if float(life.profile.states.get("hp", 0.0)) > 0:
                if life.revive():
                    _life_revive_timer.stop()
                    if _life_timer is not None:
                        _life_timer.start()
                    _log.INFO("[Life]桌宠复活，tick 计时器已重启")

        _life_revive_timer.timeout.connect(_check_revive)

    if not _life_revive_timer.isActive():
        _life_revive_timer.start(5000)
        _log.INFO("[Life]轻量复活检测计时器已启动: 5000ms")


# --------------------------------------------------------------------------- #
# 休眠（AFK）控制
# --------------------------------------------------------------------------- #

_normal_tick_interval_ms: int = 1000
_afk_tick_interval_ms: int = 5000
# 当前是否因 hide 或 AFK 而处于休眠状态
_hibernation_reason: set[str] = set()  # 可能同时存在 "hidden" 和 "afk"


def configure_tick_intervals(normal_ms: int, afk_ms: int) -> None:
    """设置正常与 AFK 的 tick 间隔（由调试设置保存后调用）。"""
    global _normal_tick_interval_ms, _afk_tick_interval_ms
    _normal_tick_interval_ms = max(100, int(normal_ms))
    _afk_tick_interval_ms = max(100, int(afk_ms))
    _log.INFO(f"[Life]tick 间隔配置 normal={_normal_tick_interval_ms}ms afk={_afk_tick_interval_ms}ms")
    # 重新应用当前实际间隔
    _apply_current_interval()


def _apply_current_interval() -> None:
    """根据当前休眠原因集合决定使用哪个 tick 间隔。"""
    if _life_timer is None or not _life_timer.isActive():
        return
    if _hibernation_reason:
        target = _afk_tick_interval_ms
    else:
        target = _normal_tick_interval_ms
    if _life_timer.interval() != target:
        _life_timer.setInterval(target)
        _log.DEBUG(f"[Life]tick 间隔已切换: {target}ms reason={_hibernation_reason or 'normal'}")


def enter_hibernation(reason: str) -> None:
    """进入休眠状态（reason: 'hidden' 或 'afk'）。"""
    _hibernation_reason.add(reason)
    _log.DEBUG(f"[Life]进入休眠 reason={reason} active={sorted(_hibernation_reason)}")
    _apply_current_interval()


def leave_hibernation(reason: str) -> None:
    """离开休眠状态（reason: 'hidden' 或 'afk'）。"""
    _hibernation_reason.discard(reason)
    _log.DEBUG(f"[Life]离开休眠 reason={reason} active={sorted(_hibernation_reason)}")
    _apply_current_interval()

