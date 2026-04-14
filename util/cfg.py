"""
配置文件管理模块
处理所有设置的保存和加载，支持热保存功能
"""
import json
from pathlib import Path
from util.log import _log

CONFIG_DIR = Path("config")
CONFIG_FILES = {
    "basic": CONFIG_DIR / "basic.cfg",
    "smart": CONFIG_DIR / "smart.cfg",
    "debug": CONFIG_DIR / "debug.cfg",
    "life": CONFIG_DIR / "life.cfg",
}

# 默认配置值
DEFAULT_CONFIGS = {
    "basic": {
        "move_timer": 200,
        "default_action_interval": 800,
        "stay_top": True,
        "default_action": True,
        "auto_load_resource_pack": False,
        "default_resource_pack": "default.json",
        "locale": "zh_cn",
    },
    "smart": {
        "check_time": 5000,
        "idle_threshold": 60,
        "max_move_range": 20,
        "walk_left_per": 2,
        "walk_right_per": 2,
        "jump_per": 5,
        "auto_move": True,
    },
    "debug": {
        "toast_duration_ms": 10000,
        "developer_mode": False,
        "locale": "zh_cn",
    },
    "life": {
        "life_enabled": False,
    },
}


def init_config_dir():
    """初始化配置文件夹，如果不存在则创建"""
    try:
        CONFIG_DIR.mkdir(exist_ok=True)
        _log.INFO(f"配置文件夹初始化成功: {CONFIG_DIR.absolute()}")
    except Exception as e:
        _log.ERROR(f"创建配置文件夹失败: {e}")
        raise


def _ensure_config_file(category: str):
    """确保配置文件存在，不存在则创建默认配置"""
    if category not in CONFIG_FILES:
        _log.WARN(f"未知的配置类别: {category}")
        return

    config_file = CONFIG_FILES[category]
    if not config_file.exists():
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIGS[category], f, indent=2, ensure_ascii=False)
            _log.INFO(f"创建默认配置文件: {config_file}")
        except Exception as e:
            _log.ERROR(f"创建配置文件失败 {config_file}: {e}")
            raise


def load_config(category: str) -> dict:
    """
    加载指定类别的配置
    
    Args:
        category: 配置类别 (basic, smart, debug, about)
        
    Returns:
        配置字典，如果文件不存在或读取失败则返回默认配置
    """
    if category not in CONFIG_FILES:
        _log.WARN(f"未知的配置类别: {category}")
        return DEFAULT_CONFIGS.get(category, {})

    config_file = CONFIG_FILES[category]
    _ensure_config_file(category)

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
            if not isinstance(config, dict):
                _log.WARN(f"配置文件格式异常 {config_file}，将使用默认配置")
                config = {}
            merged = dict(DEFAULT_CONFIGS.get(category, {}))
            merged.update(config)
            _log.INFO(f"加载配置成功: {config_file}")
            return merged
    except Exception as e:
        _log.ERROR(f"读取配置文件失败 {config_file}: {e}，使用默认配置")
        return dict(DEFAULT_CONFIGS.get(category, {}))


def save_config(category: str, config: dict):
    """
    保存指定类别的配置（热保存）
    
    Args:
        category: 配置类别 (basic, smart, debug, about)
        config: 配置字典
    """
    if category not in CONFIG_FILES:
        _log.WARN(f"未知的配置类别: {category}")
        return

    config_file = CONFIG_FILES[category]
    _ensure_config_file(category)

    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        _log.INFO(f"保存配置成功: {config_file}")
    except Exception as e:
        _log.ERROR(f"保存配置文件失败 {config_file}: {e}")
        raise


def load_all_configs() -> dict:
    """
    一次性加载所有配置
    
    Returns:
        包含所有配置的字典，键为category，值为该类别的配置
    """
    all_configs = {}
    for category in CONFIG_FILES.keys():
        all_configs[category] = load_config(category)
    return all_configs


def get_config_value(category: str, key: str, default=None):
    """
    获取单个配置值
    
    Args:
        category: 配置类别
        key: 配置键
        default: 默认值
        
    Returns:
        配置值，如果不存在则返回默认值
    """
    config = load_config(category)
    return config.get(key, default)


def set_config_value(category: str, key: str, value):
    """
    设置并保存单个配置值（热保存）
    
    Args:
        category: 配置类别
        key: 配置键
        value: 新值
    """
    config = load_config(category)
    config[key] = value
    save_config(category, config)
