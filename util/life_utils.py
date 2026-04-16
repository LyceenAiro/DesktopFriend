"""养成系统辅助工具（无 PySide6 依赖）。"""
from __future__ import annotations


def format_duration(seconds: float) -> str:
    """将秒数格式化为人类可读的时长字符串（中文）。"""
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    if minutes > 0:
        return f"{minutes}分钟{secs}秒"
    return f"{secs}秒"
