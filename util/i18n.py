import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    LANG_DIR = Path(sys._MEIPASS) / "lang"
else:
    LANG_DIR = Path("lang")
DEBUG_CONFIG_PATH = Path("config") / "debug.cfg"
BASIC_CONFIG_PATH = Path("config") / "basic.cfg"
FALLBACK_LOCALE = "zh_cn"

_cache: Dict[str, Dict[str, str]] = {}
_active_locale: str | None = None


def _load_locale_bundle(locale: str) -> Dict[str, str]:
    normalized = str(locale or "").strip().lower() or FALLBACK_LOCALE
    if normalized in _cache:
        return _cache[normalized]

    file_path = LANG_DIR / f"{normalized}.json"
    if not file_path.exists():
        _cache[normalized] = {}
        return _cache[normalized]

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache[normalized] = data if isinstance(data, dict) else {}
    except Exception:
        _cache[normalized] = {}
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
    return _active_locale


def get_available_locales() -> List[Tuple[str, str]]:
    locales: List[Tuple[str, str]] = []
    if not LANG_DIR.exists():
        return [(FALLBACK_LOCALE, FALLBACK_LOCALE)]

    for file_path in sorted(LANG_DIR.glob("*.json")):
        locale_code = file_path.stem.lower()
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
