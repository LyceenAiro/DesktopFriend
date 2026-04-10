import json
import os
from os import makedirs, path
from pathlib import Path

DEFAULT_RESOURCES_PATH_NAME = "image.json"
RESOURCES_PATH_NAME = os.getenv("DESKTOPFRIEND_RESOURCE_PACK", DEFAULT_RESOURCES_PATH_NAME)
if not RESOURCES_PATH_NAME.endswith(".json"):
    RESOURCES_PATH_NAME = f"{RESOURCES_PATH_NAME}.json"

if not path.exists("resources"):
    makedirs("resources", exist_ok=True)

LOGO_PNG = None
DEFAULT_PNG = None
DEFAULT2_PNG = None
JUMP_PNG = None
PICKUP_PNG = None
WALK_PNG = None
WALK2_PNG = None
WALK3_PNG = None
WALK4_PNG = None
NONE_PNG = None
HIDE_GIF = None

__all__ = [
    "LOGO_PNG",
    "DEFAULT_PNG",
    "DEFAULT2_PNG",
    "JUMP_PNG",
    "PICKUP_PNG",
    "WALK_PNG",
    "WALK2_PNG",
    "WALK3_PNG",
    "WALK4_PNG",
    "NONE_PNG",
    "HIDE_GIF",
]

_REQUIRED_KEYS = (
    "LOGO_PNG",
    "DEFAULT_PNG",
    "DEFAULT2_PNG",
    "JUMP_PNG",
    "PICKUP_PNG",
    "WALK_PNG",
    "WALK2_PNG",
    "WALK3_PNG",
    "WALK4_PNG",
    "NONE_PNG",
    "HIDE_GIF",
)


def _normalize_pack_name(resource_pack: str) -> str:
    if not resource_pack:
        return DEFAULT_RESOURCES_PATH_NAME
    pack_name = str(resource_pack)
    if not pack_name.endswith(".json"):
        pack_name = f"{pack_name}.json"
    return pack_name


def get_available_resource_packs(resources_dir: str = "resources"):
    resources_path = Path(resources_dir)
    if not resources_path.exists():
        return []
    return sorted([json_file.name for json_file in resources_path.glob("*.json")])


def get_resource_pack_display_name(resource_pack: str, resources_dir: str = "resources") -> str:
    pack_file_name = _normalize_pack_name(resource_pack)
    resource_path = Path(resources_dir) / pack_file_name
    fallback_name = Path(pack_file_name).stem

    try:
        with open(resource_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return fallback_name

    if isinstance(data, dict):
        pack_name = data.get("PACK_NAME")
        if isinstance(pack_name, str) and pack_name.strip():
            return pack_name.strip()
    return fallback_name


def get_resource_pack_name() -> str:
    return RESOURCES_PATH_NAME


def set_resource_pack(resource_pack: str):
    global RESOURCES_PATH_NAME
    RESOURCES_PATH_NAME = _normalize_pack_name(resource_pack)
    return _load_image_resources()


def _load_image_resources():
    resource_path = Path("resources") / RESOURCES_PATH_NAME
    try:
        with open(resource_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Missing image resources JSON at {RESOURCES_PATH_NAME}. "
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid image resources JSON format: expected object, got {type(data).__name__}."
        )

    missing_keys = [key for key in _REQUIRED_KEYS if key not in data]
    if missing_keys:
        raise ValueError(
            f"Invalid image resources JSON format: missing required keys {missing_keys}."
        )

    globals().update(data)
    globals()["__all__"] = tuple(data.keys())
    return data

