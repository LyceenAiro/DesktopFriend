import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from util.log import _log

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    LANG_DIR = Path(sys._MEIPASS) / "lang"
else:
    LANG_DIR = Path("lang")
DEBUG_CONFIG_PATH = Path("config") / "debug.cfg"
BASIC_CONFIG_PATH = Path("config") / "basic.cfg"
FALLBACK_LOCALE = "zh_cn"

_cache: Dict[str, Dict[str, str]] = {}
_active_locale: str | None = None
_extra_lang_dirs: List[Path] = []


def _invalidate_i18n_cache() -> None:
    _cache.clear()


def attach_lang_dir(lang_dir: str | Path) -> bool:
    path = Path(lang_dir)
    if path in _extra_lang_dirs:
        return False
    _extra_lang_dirs.append(path)
    _invalidate_i18n_cache()
    _log.DEBUG(f"[i18n]附加语言目录: {path}")
    return True


def detach_lang_dir(lang_dir: str | Path) -> bool:
    path = Path(lang_dir)
    if path not in _extra_lang_dirs:
        return False
    _extra_lang_dirs.remove(path)
    _invalidate_i18n_cache()
    _log.DEBUG(f"[i18n]移除语言目录: {path}")
    return True


def get_extra_lang_dirs() -> List[Path]:
    return list(_extra_lang_dirs)


def attach_mod_lang_dirs_early(mod_root: str | Path = "mod") -> int:
    """Scan mod directories and attach their lang/ subdirectories early.

    Call this before any UI module imports so that class-level
    ``tab_name = tr(...)`` attributes pick up mod translations.
    Returns the number of lang dirs attached.
    """
    root = Path(mod_root)
    if not root.exists():
        return 0
    count = 0
    for mod_dir in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if mod_dir.is_dir():
            lang_dir = mod_dir / "lang"
            if lang_dir.exists() and attach_lang_dir(lang_dir):
                count += 1
    return count


def _load_locale_bundle(locale: str) -> Dict[str, str]:
    normalized = str(locale or "").strip().lower() or FALLBACK_LOCALE
    if normalized in _cache:
        return _cache[normalized]

    merged: Dict[str, str] = {}
    search_dirs = [LANG_DIR, *_extra_lang_dirs]
    for lang_dir in search_dirs:
        file_path = lang_dir / f"{normalized}.json"
        if not file_path.exists():
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                merged.update({str(k): str(v) if not isinstance(v, str) else v for k, v in data.items()})
        except Exception as exc:
            _log.WARN(f"[i18n]加载语言文件失败: locale={normalized} path={file_path} error={exc}")
            continue

    _cache[normalized] = merged
    return _cache[normalized]


def get_locale() -> str:
    global _active_locale
    if _active_locale:
        return _active_locale

    locale = FALLBACK_LOCALE
    try:
        if BASIC_CONFIG_PATH.exists():
            with open(BASIC_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            if isinstance(config, dict):
                locale = str(config.get("locale", FALLBACK_LOCALE)).strip().lower() or FALLBACK_LOCALE
        elif DEBUG_CONFIG_PATH.exists():
            with open(DEBUG_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            if isinstance(config, dict):
                locale = str(config.get("locale", FALLBACK_LOCALE)).strip().lower() or FALLBACK_LOCALE
    except Exception:
        locale = FALLBACK_LOCALE
    _active_locale = locale or FALLBACK_LOCALE
    _log.INFO(f"[i18n]当前语言环境: {_active_locale}")
    return _active_locale


def get_available_locales() -> List[Tuple[str, str]]:
    locales: List[Tuple[str, str]] = []
    locale_codes: set[str] = set()
    for lang_dir in [LANG_DIR, *_extra_lang_dirs]:
        if not lang_dir.exists():
            continue
        for file_path in sorted(lang_dir.glob("*.json")):
            locale_codes.add(file_path.stem.lower())

    for locale_code in sorted(locale_codes):
        bundle = _load_locale_bundle(locale_code)
        display_name = str(bundle.get("lang_name", locale_code))
        locales.append((locale_code, display_name))

    if not locales:
        locales.append((FALLBACK_LOCALE, FALLBACK_LOCALE))

    return locales


def tr(key: str, default: str = "", **kwargs) -> str:
    locale = get_locale()
    active_bundle = _load_locale_bundle(locale)
    fallback_bundle = _load_locale_bundle(FALLBACK_LOCALE)

    template = active_bundle.get(key)
    if template is None:
        template = fallback_bundle.get(key)
    if template is None:
        template = default or key

    if kwargs:
        try:
            rendered = str(template).format(**kwargs)
        except Exception:
            rendered = str(template)
    else:
        rendered = str(template)

    # Allow language files to use literal "\\n" / "\\t" and still render as control chars.
    return rendered.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
