from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BASE_STATES = ("hp", "happy", "psc", "energy")
BASE_ATTRS = ("vit", "str", "spd", "agi", "spi", "int", "ill")

STACK_RULES = {"add", "noadd", "refresh"}


def _normalize_state_keys(state_keys: tuple[str, ...] | list[str] | set[str] | None) -> set[str]:
    if not state_keys:
        return set(BASE_STATES)
    return {str(k).strip() for k in state_keys if str(k).strip()}


def _normalize_attr_keys(attr_keys: tuple[str, ...] | list[str] | set[str] | None) -> set[str]:
    if not attr_keys:
        return set(BASE_ATTRS)
    return {str(k).strip() for k in attr_keys if str(k).strip()}


def _normalize_nutrition_keys(nutrition_keys: tuple[str, ...] | list[str] | set[str] | None) -> set[str]:
    if not nutrition_keys:
        return set()
    return {str(k).strip() for k in nutrition_keys if str(k).strip()}


@dataclass
class ValidationIssue:
    level: str
    message: str
    source: str
    record_id: str
    field: str


def _is_number_like(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_percent_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text.endswith("%"):
        return False
    try:
        float(text[:-1])
        return True
    except Exception:
        return False


def _validate_periodic_key(
    key: str,
    value: Any,
    issues: list[ValidationIssue],
    source: str,
    record_id: str,
    state_keys: set[str],
    nutrition_keys: set[str] | None = None,
) -> bool:
    periodic_keys = state_keys | (nutrition_keys or set())
    if key.endswith("s") and key[:-1] in periodic_keys:
        if not _is_number_like(value):
            issues.append(ValidationIssue("error", "持续效果值必须为数值", source, record_id, key))
        return True
    if key.endswith("st") and key[:-2] in state_keys:
        if not isinstance(value, int):
            issues.append(ValidationIssue("error", "持续时长必须为整数 tick", source, record_id, key))
        return True
    if key.endswith("sr") and key[:-2] in state_keys:
        if str(value).lower() not in STACK_RULES:
            issues.append(ValidationIssue("error", "叠加规则仅支持 add/noadd/refresh", source, record_id, key))
        return True
    return False


def _validate_cap_modifier(
    key: str,
    value: Any,
    issues: list[ValidationIssue],
    source: str,
    record_id: str,
    state_keys: set[str],
    attr_keys: set[str],
) -> bool:
    for suffix in ("_max", "_min", "_max2"):
        if key.endswith(suffix):
            base = key[: -len(suffix)]
            if base not in state_keys and base not in attr_keys:
                issues.append(ValidationIssue("warn", "上下限字段基础名不在已知状态/属性中", source, record_id, key))
            if not (_is_number_like(value) or _is_percent_string(value)):
                issues.append(ValidationIssue("error", "上下限字段值应为数值或百分比字符串", source, record_id, key))
            return True
    return False


def validate_buff_record(
    record: dict[str, Any],
    source: str,
    state_keys: tuple[str, ...] | list[str] | set[str] | None = None,
    attr_keys: tuple[str, ...] | list[str] | set[str] | None = None,
    nutrition_keys: tuple[str, ...] | list[str] | set[str] | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    record_id = str(record.get("id") or record.get("name") or "<unknown>")
    valid_states = _normalize_state_keys(state_keys)
    valid_attrs = _normalize_attr_keys(attr_keys)
    valid_nutrition = _normalize_nutrition_keys(nutrition_keys)

    if "id" not in record or not str(record.get("id", "")).strip():
        issues.append(ValidationIssue("error", "buff 缺少 id", source, record_id, "id"))
    if "name" not in record or not str(record.get("name", "")).strip():
        issues.append(ValidationIssue("warn", "buff 缺少 name", source, record_id, "name"))

    if "desc" in record and not isinstance(record["desc"], str):
        issues.append(ValidationIssue("error", "desc 必须是字符串", source, record_id, "desc"))
    if "description" in record and not isinstance(record["description"], str):
        issues.append(ValidationIssue("error", "description 必须是字符串", source, record_id, "description"))
    if "name_i18n_key" in record and not isinstance(record["name_i18n_key"], str):
        issues.append(ValidationIssue("error", "name_i18n_key 必须是字符串", source, record_id, "name_i18n_key"))
    if "desc_i18n_key" in record and not isinstance(record["desc_i18n_key"], str):
        issues.append(ValidationIssue("error", "desc_i18n_key 必须是字符串", source, record_id, "desc_i18n_key"))
    if "description_i18n_key" in record and not isinstance(record["description_i18n_key"], str):
        issues.append(
            ValidationIssue("error", "description_i18n_key 必须是字符串", source, record_id, "description_i18n_key")
        )

    if "status" in record and not isinstance(record["status"], list):
        issues.append(ValidationIssue("error", "status 规则必须是列表", source, record_id, "status"))

    for key, value in record.items():
        if key in {
            "id",
            "name",
            "desc",
            "description",
            "name_i18n_key",
            "desc_i18n_key",
            "description_i18n_key",
            "attribute",
            "status",
            "_classes",
        }:
            continue

        if key == "chance":
            if not _is_number_like(value):
                issues.append(ValidationIssue("error", "chance 必须为数值", source, record_id, key))
            continue

        if key in valid_states or key in valid_attrs:
            if not _is_number_like(value):
                issues.append(ValidationIssue("error", "状态/属性即时値必须为数値", source, record_id, key))
            continue

        if _validate_periodic_key(key, value, issues, source, record_id, valid_states, valid_nutrition):
            continue

        if _validate_cap_modifier(key, value, issues, source, record_id, valid_states, valid_attrs):
            continue

        issues.append(ValidationIssue("warn", "未识别字段，将按原始逻辑透传", source, record_id, key))

    return issues


def validate_item_record(
    record: dict[str, Any],
    source: str,
    state_keys: tuple[str, ...] | list[str] | set[str] | None = None,
    attr_keys: tuple[str, ...] | list[str] | set[str] | None = None,
    nutrition_keys: tuple[str, ...] | list[str] | set[str] | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    record_id = str(record.get("id") or record.get("name") or "<unknown>")
    valid_states = _normalize_state_keys(state_keys)
    valid_attrs = _normalize_attr_keys(attr_keys)
    valid_nutrition = _normalize_nutrition_keys(nutrition_keys)

    if "id" not in record or not str(record.get("id", "")).strip():
        issues.append(ValidationIssue("error", "item 缺少 id", source, record_id, "id"))
    if "name" not in record or not str(record.get("name", "")).strip():
        issues.append(ValidationIssue("warn", "item 缺少 name", source, record_id, "name"))

    if "usable" in record and not isinstance(record["usable"], bool):
        issues.append(ValidationIssue("error", "usable 必须是布尔值", source, record_id, "usable"))
    if "consumable" in record and not isinstance(record["consumable"], bool):
        issues.append(ValidationIssue("error", "consumable 必须是布尔值", source, record_id, "consumable"))

    if "desc" in record and not isinstance(record["desc"], str):
        issues.append(ValidationIssue("error", "desc 必须是字符串", source, record_id, "desc"))
    if "description" in record and not isinstance(record["description"], str):
        issues.append(ValidationIssue("error", "description 必须是字符串", source, record_id, "description"))
    if "name_i18n_key" in record and not isinstance(record["name_i18n_key"], str):
        issues.append(ValidationIssue("error", "name_i18n_key 必须是字符串", source, record_id, "name_i18n_key"))
    if "desc_i18n_key" in record and not isinstance(record["desc_i18n_key"], str):
        issues.append(ValidationIssue("error", "desc_i18n_key 必须是字符串", source, record_id, "desc_i18n_key"))
    if "description_i18n_key" in record and not isinstance(record["description_i18n_key"], str):
        issues.append(
            ValidationIssue("error", "description_i18n_key 必须是字符串", source, record_id, "description_i18n_key")
        )

    for key, value in record.items():
        if key in {
            "id",
            "name",
            "desc",
            "description",
            "name_i18n_key",
            "desc_i18n_key",
            "description_i18n_key",
            "usable",
            "category",
            "consumable",
            "_classes",
        }:
            continue

        if key == "cooldown_s":
            if not _is_number_like(value):
                issues.append(ValidationIssue("error", "cooldown_s 必须为数值", source, record_id, key))
            continue

        if key == "chance":
            if not _is_number_like(value):
                issues.append(ValidationIssue("error", "chance 必须为数值", source, record_id, key))
            continue

        if key == "buff_refs":
            if not isinstance(value, list):
                issues.append(ValidationIssue("error", "buff_refs 必须是列表", source, record_id, key))
            elif not all(isinstance(ref, str) for ref in value):
                issues.append(ValidationIssue("error", "buff_refs 列表中的每个元素必须是字符串", source, record_id, key))
            continue

        if key == "nutrition":
            if not isinstance(value, dict):
                issues.append(ValidationIssue("error", "nutrition 必须是字典", source, record_id, key))
                continue
            for nutrition_key, nutrition_value in value.items():
                nutrition_id = str(nutrition_key).strip()
                if not nutrition_id:
                    issues.append(ValidationIssue("error", "nutrition 包含空键名", source, record_id, key))
                    continue
                if valid_nutrition and nutrition_id not in valid_nutrition:
                    issues.append(ValidationIssue("warn", "nutrition 键未注册，将在运行时忽略", source, record_id, f"nutrition.{nutrition_id}"))
                if not _is_number_like(nutrition_value):
                    issues.append(
                        ValidationIssue(
                            "error",
                            "nutrition 值必须为数值",
                            source,
                            record_id,
                            f"nutrition.{nutrition_id}",
                        )
                    )
            continue

        if key in valid_states or key in valid_attrs:
            if not _is_number_like(value):
                issues.append(ValidationIssue("error", "状态/属性即时值必须为数值", source, record_id, key))
            continue

        if _validate_periodic_key(key, value, issues, source, record_id, valid_states):
            continue

        if _validate_cap_modifier(key, value, issues, source, record_id, valid_states, valid_attrs):
            continue

        issues.append(ValidationIssue("warn", "未识别字段，将按原始逻辑透传", source, record_id, key))

    return issues


# ── Event system validators ─────────────────────────────────────────

_EVENT_GUARANTEED_KEYS = {"items", "buffs", "outcomes"}


def _validate_guaranteed_block(
    block: Any,
    issues: list[ValidationIssue],
    source: str,
    record_id: str,
    field_prefix: str,
) -> None:
    if not isinstance(block, dict):
        issues.append(ValidationIssue("error", f"{field_prefix} 必须是字典", source, record_id, field_prefix))
        return
    for key in block:
        if key not in _EVENT_GUARANTEED_KEYS:
            issues.append(ValidationIssue("warn", f"{field_prefix} 包含未知键: {key}", source, record_id, f"{field_prefix}.{key}"))
    items = block.get("items", [])
    if not isinstance(items, list):
        issues.append(ValidationIssue("error", f"{field_prefix}.items 必须是列表", source, record_id, f"{field_prefix}.items"))
    else:
        for i, entry in enumerate(items):
            if not isinstance(entry, dict):
                issues.append(ValidationIssue("error", f"{field_prefix}.items[{i}] 必须是字典", source, record_id, f"{field_prefix}.items"))
            elif not str(entry.get("id") or "").strip():
                issues.append(ValidationIssue("error", f"{field_prefix}.items[{i}] 缺少 id", source, record_id, f"{field_prefix}.items"))
    buffs = block.get("buffs", [])
    if not isinstance(buffs, list):
        issues.append(ValidationIssue("error", f"{field_prefix}.buffs 必须是列表", source, record_id, f"{field_prefix}.buffs"))
    outcomes = block.get("outcomes", [])
    if not isinstance(outcomes, list):
        issues.append(ValidationIssue("error", f"{field_prefix}.outcomes 必须是列表", source, record_id, f"{field_prefix}.outcomes"))


def _validate_random_pools(
    pools: Any,
    issues: list[ValidationIssue],
    source: str,
    record_id: str,
    field_prefix: str,
) -> None:
    if not isinstance(pools, list):
        issues.append(ValidationIssue("error", f"{field_prefix} 必须是列表", source, record_id, field_prefix))
        return
    for pi, pool in enumerate(pools):
        pool_path = f"{field_prefix}[{pi}]"
        if not isinstance(pool, dict):
            issues.append(ValidationIssue("error", f"{pool_path} 必须是字典", source, record_id, pool_path))
            continue
        entries = pool.get("entries")
        if not isinstance(entries, list):
            issues.append(ValidationIssue("error", f"{pool_path}.entries 必须是列表", source, record_id, f"{pool_path}.entries"))
            continue
        for ei, entry in enumerate(entries):
            entry_path = f"{pool_path}.entries[{ei}]"
            if not isinstance(entry, dict):
                issues.append(ValidationIssue("error", f"{entry_path} 必须是字典", source, record_id, entry_path))
                continue
            entry_type = str(entry.get("type") or "").strip().lower()
            if entry_type not in ("item", "buff", "outcome"):
                issues.append(ValidationIssue("error", f"{entry_path}.type 必须为 item/buff/outcome", source, record_id, f"{entry_path}.type"))
            if not str(entry.get("id") or "").strip():
                issues.append(ValidationIssue("error", f"{entry_path} 缺少 id", source, record_id, f"{entry_path}.id"))
            chance = entry.get("chance")
            if chance is not None and not _is_number_like(chance):
                issues.append(ValidationIssue("error", f"{entry_path}.chance 必须为数值", source, record_id, f"{entry_path}.chance"))


def validate_event_trigger_record(
    record: dict[str, Any],
    source: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    record_id = str(record.get("id") or record.get("name") or "<unknown>")

    if "id" not in record or not str(record.get("id", "")).strip():
        issues.append(ValidationIssue("error", "event_trigger 缺少 id", source, record_id, "id"))
    if "name" not in record or not str(record.get("name", "")).strip():
        issues.append(ValidationIssue("warn", "event_trigger 缺少 name", source, record_id, "name"))

    for str_field in ("desc", "description", "name_i18n_key", "desc_i18n_key", "description_i18n_key"):
        if str_field in record and not isinstance(record[str_field], str):
            issues.append(ValidationIssue("error", f"{str_field} 必须是字符串", source, record_id, str_field))

    if "cooldown_s" in record and not _is_number_like(record["cooldown_s"]):
        issues.append(ValidationIssue("error", "cooldown_s 必须为数值", source, record_id, "cooldown_s"))

    if "duration_s" in record and not _is_number_like(record["duration_s"]):
        issues.append(ValidationIssue("error", "duration_s 必须为数值", source, record_id, "duration_s"))

    mutex = record.get("mutex")
    if mutex is not None:
        if not isinstance(mutex, list):
            issues.append(ValidationIssue("error", "mutex 必须是列表", source, record_id, "mutex"))
        elif not all(isinstance(m, str) for m in mutex):
            issues.append(ValidationIssue("error", "mutex 列表中的每个元素必须是字符串", source, record_id, "mutex"))

    def _validate_item_condition(field: str) -> None:
        value = record.get(field)
        if value is None:
            return
        if isinstance(value, str):
            if not value.strip():
                issues.append(ValidationIssue("error", f"{field} 不能为空字符串", source, record_id, field))
            return
        if isinstance(value, list):
            if not all(isinstance(item, str) and item.strip() for item in value):
                issues.append(ValidationIssue("error", f"{field} 列表中的每个元素必须是非空字符串", source, record_id, field))
            return
        issues.append(ValidationIssue("error", f"{field} 必须是字符串或字符串列表", source, record_id, field))

    _validate_item_condition("requires_item")
    _validate_item_condition("requires_no_item")

    if "guaranteed" in record:
        _validate_guaranteed_block(record["guaranteed"], issues, source, record_id, "guaranteed")

    if "random_pools" in record:
        _validate_random_pools(record["random_pools"], issues, source, record_id, "random_pools")

    known_keys = {
        "id", "name", "desc", "description",
        "name_i18n_key", "desc_i18n_key", "description_i18n_key",
        "cooldown_s", "duration_s", "mutex", "guaranteed", "random_pools",
        "requires_item", "requires_no_item",
        "_classes",
    }
    for key in record:
        if key not in known_keys:
            issues.append(ValidationIssue("warn", "未识别字段", source, record_id, key))

    return issues


def validate_event_outcome_record(
    record: dict[str, Any],
    source: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    record_id = str(record.get("id") or record.get("name") or "<unknown>")

    if "id" not in record or not str(record.get("id", "")).strip():
        issues.append(ValidationIssue("error", "event_outcome 缺少 id", source, record_id, "id"))
    if "name" not in record or not str(record.get("name", "")).strip():
        issues.append(ValidationIssue("warn", "event_outcome 缺少 name", source, record_id, "name"))

    for str_field in ("desc", "description", "name_i18n_key", "desc_i18n_key", "description_i18n_key"):
        if str_field in record and not isinstance(record[str_field], str):
            issues.append(ValidationIssue("error", f"{str_field} 必须是字符串", source, record_id, str_field))

    if "guaranteed" in record:
        _validate_guaranteed_block(record["guaranteed"], issues, source, record_id, "guaranteed")

    if "random_pools" in record:
        _validate_random_pools(record["random_pools"], issues, source, record_id, "random_pools")

    known_keys = {
        "id", "name", "desc", "description",
        "name_i18n_key", "desc_i18n_key", "description_i18n_key",
        "guaranteed", "random_pools", "effects",
    }
    for key in record:
        if key not in known_keys:
            issues.append(ValidationIssue("warn", "未识别字段", source, record_id, key))

    return issues
