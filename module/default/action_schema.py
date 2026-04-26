from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationIssue:
    level: str  # "error" | "warn"
    message: str
    field: str = ""


_VALID_PLAY_MODES = {"once", "loop", "random"}
_VALID_BLOCK_MODES = {"exclusive", "sequence", "normal"}


def validate_action_record(record: dict[str, Any]) -> list[ValidationIssue]:
    """校驗单个动作 JSON 记录的字段合法性。

    Returns:
        list[ValidationIssue]: 校验问题列表（error 级别表示不可注册，warn 级别表示建议修复）。
    """
    issues: list[ValidationIssue] = []
    action_id = str(record.get("id", "")).strip()

    # --- id ---
    if not action_id:
        issues.append(ValidationIssue("error", "动作 id 不能为空", "id"))
    elif action_id.startswith("vanilla."):
        issues.append(ValidationIssue("error", "动作 id 不能以 'vanilla.' 开头（保留给原版动画）", "id"))

    # --- image_base64 ---
    image_list = record.get("image_base64")
    if not isinstance(image_list, list) or len(image_list) == 0:
        issues.append(ValidationIssue("error", "image_base64 必须为非空列表", "image_base64"))
    else:
        img_count = len(image_list)

        # --- frames ---
        frames = record.get("frames")
        if frames is not None:
            try:
                fv = int(frames)
                if fv < 1:
                    issues.append(ValidationIssue("error", "frames 必须 >= 1", "frames"))
                elif fv > img_count:
                    issues.append(ValidationIssue("error", f"image_base64 数量不足: need={fv} have={img_count}", "frames"))
            except (TypeError, ValueError):
                issues.append(ValidationIssue("error", "frames 必须为整数", "frames"))

        # --- animation_sorting ---
        sorting = record.get("animation_sorting")
        if sorting is not None:
            if not isinstance(sorting, list):
                issues.append(ValidationIssue("error", "animation_sorting 必须是列表", "animation_sorting"))
            else:
                for i, idx in enumerate(sorting):
                    if not isinstance(idx, int):
                        issues.append(ValidationIssue("error", f"animation_sorting[{i}] 必须为整数", "animation_sorting"))
                    elif idx < 0 or idx >= img_count:
                        issues.append(ValidationIssue("error", f"animation_sorting[{i}]={idx} 超出 image_base64 范围 [0,{img_count - 1}]", "animation_sorting"))

    # --- play_mode ---
    play_mode = str(record.get("play_mode", "once")).strip().lower()
    if play_mode not in _VALID_PLAY_MODES:
        issues.append(ValidationIssue("error", f"play_mode 必须为 once/loop/random，当前值: {play_mode}", "play_mode"))

    # --- random_per ---
    random_per = record.get("random_per")
    if play_mode == "random":
        if random_per is None:
            issues.append(ValidationIssue("error", "random 模式必须填写 random_per", "random_per"))
        else:
            try:
                rp = float(random_per)
                if rp <= 0:
                    issues.append(ValidationIssue("error", "random_per 必须 > 0", "random_per"))
                elif rp > 100:
                    issues.append(ValidationIssue("error", "random_per 不能超过 100", "random_per"))
            except (TypeError, ValueError):
                issues.append(ValidationIssue("error", "random_per 必须为数值", "random_per"))
    elif random_per is not None:
        # 非 random 模式下提供 random_per -> warn
        issues.append(ValidationIssue("warn", f"play_mode={play_mode} 时 random_per 将被忽略", "random_per"))

    # --- block_mode ---
    block_mode = str(record.get("block_mode", "normal")).strip().lower()
    if block_mode not in _VALID_BLOCK_MODES:
        issues.append(ValidationIssue("error", f"block_mode 必须为 exclusive/sequence/normal，当前值: {block_mode}", "block_mode"))

    # --- frame_interval_ms ---
    interval = record.get("frame_interval_ms")
    if interval is not None:
        try:
            iv = int(interval)
            if iv <= 0:
                issues.append(ValidationIssue("error", "frame_interval_ms 必须 > 0", "frame_interval_ms"))
        except (TypeError, ValueError):
            issues.append(ValidationIssue("error", "frame_interval_ms 必须为整数", "frame_interval_ms"))

    # --- name (optional) ---
    if "name" in record and not isinstance(record["name"], str):
        issues.append(ValidationIssue("warn", "name 必须为字符串", "name"))
    if "desc" in record and not isinstance(record["desc"], str):
        issues.append(ValidationIssue("warn", "desc 必须为字符串", "desc"))

    return issues
