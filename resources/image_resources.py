import json
from os import makedirs, path
from pathlib import Path

RESOURCES_PATH_NAME = "image.json"

if path.exists("resources"):
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


def _load_image_resources():
    try:
        with open(f"resources/{RESOURCES_PATH_NAME}", "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Missing image resources JSON at {RESOURCES_PATH_NAME}. "
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid image resources JSON format: expected object, got {type(data).__name__}."
        )

    globals().update(data)
    globals()["__all__"] = tuple(data.keys())
    return data


_load_image_resources()
