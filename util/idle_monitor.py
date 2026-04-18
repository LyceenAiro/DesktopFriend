"""
idle_monitor.py — 系统空闲时间监测，用于驱动生命系统休眠模式。

检测逻辑：
  - Windows：通过 GetLastInputInfo 获取系统最后一次鼠标/键盘输入距今的时长。
  - 其他平台：不启用（无法无侵入地检测系统级空闲）。

每 60 秒轮询一次；当空闲时长 >= afk_timeout_s 时进入 AFK 休眠，
恢复输入后立即退出 AFK 休眠。
"""

from __future__ import annotations

import sys
import ctypes
from PySide6.QtCore import QTimer

from util.log import _log

# 轮询间隔（ms）——不需要太频繁，60s 足够
_POLL_INTERVAL_MS = 60_000

_timer: QTimer | None = None
_afk_timeout_s: int = 3600
_is_afk: bool = False


class _LASTINPUTINFO(ctypes.Structure):  # type: ignore[misc]
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]


def _get_idle_seconds() -> float:
    """返回系统距上次鼠标/键盘输入经过的秒数。仅 Windows 有效，其他平台返回 0。"""
    if sys.platform != "win32":
        return 0.0
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return max(0.0, millis / 1000.0)
    except Exception:
        return 0.0


def _on_poll() -> None:
    global _is_afk
    from module.life.runtime import enter_hibernation, leave_hibernation

    idle_s = _get_idle_seconds()
    if not _is_afk and idle_s >= _afk_timeout_s:
        _is_afk = True
        enter_hibernation("afk")
        _log.INFO(f"[Life][AFK]检测到系统空闲 {idle_s:.0f}s，进入 AFK 休眠")
    elif _is_afk and idle_s < _afk_timeout_s:
        _is_afk = False
        leave_hibernation("afk")
        _log.INFO("[Life][AFK]检测到用户活跃，退出 AFK 休眠")


class IdleMonitor:
    @staticmethod
    def start(parent=None, afk_timeout_s: int = 3600) -> None:
        global _timer, _afk_timeout_s
        _afk_timeout_s = max(60, int(afk_timeout_s))

        if sys.platform != "win32":
            _log.DEBUG("[Life][AFK]非 Windows 平台，空闲监测不启用")
            return

        if _timer is not None:
            _timer.setInterval(_POLL_INTERVAL_MS)
            return

        _timer = QTimer(parent)
        _timer.setInterval(_POLL_INTERVAL_MS)
        _timer.timeout.connect(_on_poll)
        _timer.start()
        _log.INFO(f"[Life][AFK]空闲监测已启动，超时阈值={_afk_timeout_s}s，轮询={_POLL_INTERVAL_MS}ms")

    @staticmethod
    def reconfigure(afk_timeout_s: int) -> None:
        """运行时更新超时阈值（从设置保存后调用）。"""
        global _afk_timeout_s
        _afk_timeout_s = max(60, int(afk_timeout_s))
        _log.DEBUG(f"[Life][AFK]超时阈值已更新: {_afk_timeout_s}s")
