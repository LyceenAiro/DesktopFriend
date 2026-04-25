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
    nutrition_keys: set[str] | None = None,
) -> bool:
    for suffix in ("_max", "_min", "_max2"):
        if key.endswith(suffix):
            base = key[: -len(suffix)]
            if base not in state_keys and base not in attr_keys and base not in (nutrition_keys or set()):
                issues.append(ValidationIssue("warn", "上下限字段基础名不在已知状态/属性/营养中", source, record_id, key))
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
            # 条件与标签系统（Phase 1）
            "consume_self",
            "requires_buff",
            "requires_no_buff",
            "restrict_item_tags",
            "restrict_trigger_tags",
            "tags",
            "fail_messages",
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

        if _validate_cap_modifier(key, value, issues, source, record_id, valid_states, valid_attrs, valid_nutrition):
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
    if "unique" in record and not isinstance(record["unique"], bool):
        issues.append(ValidationIssue("error", "unique 必须是布尔值", source, record_id, "unique"))
    if "passive_attr_bonus" in record:
        pab = record["passive_attr_bonus"]
        if not isinstance(pab, dict):
            issues.append(ValidationIssue("error", "passive_attr_bonus 必须是字典", source, record_id, "passive_attr_bonus"))
        else:
            for _ak, _av in pab.items():
                if not isinstance(_av, (int, float)):
                    issues.append(ValidationIssue(
                        "error",
                        f"passive_attr_bonus[{_ak}] 必须是数値",
                        source, record_id, "passive_attr_bonus",
                    ))
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
            "icon_base64",
            "usable",
            "unique",
            "passive_attr_bonus",
            "category",
            "consumable",
            "_classes",
            # 条件与标签系统（Phase 1）
            "requires_buff",
            "requires_no_buff",
            "tags",
            "fail_messages",
            # 等级/经验联动（Phase 4）
            "exp",
            "passive_exp_bonus",
            "min_level",
            "permanent_attr_delta",
            "attr_exp",
            "clear_buffs",
        }:
            continue

        if key == "clear_buffs":
            if isinstance(value, str):
                if not value.strip():
                    issues.append(ValidationIssue("error", "clear_buffs 不能为空字符串", source, record_id, key))
                continue
            if isinstance(value, list):
                if not all(isinstance(v, str) and v.strip() for v in value):
                    issues.append(ValidationIssue("error", "clear_buffs 列表元素必须是非空字符串", source, record_id, key))
                continue
            issues.append(ValidationIssue("error", "clear_buffs 必须是字符串或字符串列表", source, record_id, key))
            continue

        if key == "exp":
            if not _is_number_like(value):
                issues.append(ValidationIssue("error", "exp 必须为数值", source, record_id, key))
            continue

        if key == "passive_exp_bonus":
            if not _is_number_like(value):
                issues.append(ValidationIssue("error", "passive_exp_bonus 必须为数值", source, record_id, key))
            continue

        if key == "min_level":
            if not isinstance(value, int) or value < 0:
                issues.append(ValidationIssue("error", "min_level 必须为非负整数", source, record_id, key))
            continue

        if key == "permanent_attr_delta":
            if not isinstance(value, dict):
                issues.append(ValidationIssue("error", "permanent_attr_delta 必须是字典", source, record_id, key))
            else:
                for _k, _v in value.items():
                    if not isinstance(_v, (int, float)):
                        issues.append(ValidationIssue("error", f"permanent_attr_delta[{_k}] 必须为数值", source, record_id, key))
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

        if _validate_cap_modifier(key, value, issues, source, record_id, valid_states, valid_attrs, valid_nutrition):
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
            flat_bonus = entry.get("flat_bonus")
            if flat_bonus is not None and not _is_number_like(flat_bonus):
                issues.append(ValidationIssue("error", f"{entry_path}.flat_bonus 必须为数值", source, record_id, f"{entry_path}.flat_bonus"))
            attr_bonus = entry.get("attr_bonus")
            if attr_bonus is not None and not isinstance(attr_bonus, dict):
                issues.append(ValidationIssue("error", f"{entry_path}.attr_bonus 必须是字典", source, record_id, f"{entry_path}.attr_bonus"))
            state_bonus = entry.get("state_bonus")
            if state_bonus is not None:
                if not isinstance(state_bonus, dict):
                    issues.append(ValidationIssue("error", f"{entry_path}.state_bonus 必须是字典", source, record_id, f"{entry_path}.state_bonus"))
                else:
                    for skey, sval in state_bonus.items():
                        if not str(skey).strip():
                            issues.append(ValidationIssue("error", f"{entry_path}.state_bonus 包含空键名", source, record_id, f"{entry_path}.state_bonus"))
                            continue
                        if not _is_number_like(sval):
                            issues.append(ValidationIssue("error", f"{entry_path}.state_bonus.{skey} 必须为数值", source, record_id, f"{entry_path}.state_bonus.{skey}"))

        fallback = pool.get("fallback")
        if fallback is not None:
            if not isinstance(fallback, dict):
                issues.append(ValidationIssue("error", f"{pool_path}.fallback 必须是字典", source, record_id, f"{pool_path}.fallback"))
            else:
                fb_type = str(fallback.get("type") or "").strip().lower()
                if fb_type not in ("item", "buff", "outcome"):
                    issues.append(ValidationIssue("error", f"{pool_path}.fallback.type 必须为 item/buff/outcome", source, record_id, f"{pool_path}.fallback.type"))
                if not str(fallback.get("id") or "").strip():
                    issues.append(ValidationIssue("error", f"{pool_path}.fallback.id 不能为空", source, record_id, f"{pool_path}.fallback.id"))
                if "count" in fallback and not isinstance(fallback.get("count"), int):
                    issues.append(ValidationIssue("error", f"{pool_path}.fallback.count 必须为整数", source, record_id, f"{pool_path}.fallback.count"))


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

    costs = record.get("costs")
    if costs is not None:
        if not isinstance(costs, dict):
            issues.append(ValidationIssue("error", "costs 必须是字典", source, record_id, "costs"))
        else:
            for cost_key, cost_val in costs.items():
                if not str(cost_key).strip():
                    issues.append(ValidationIssue("error", "costs 包含空键名", source, record_id, "costs"))
                    continue
                if not _is_number_like(cost_val):
                    issues.append(
                        ValidationIssue(
                            "error",
                            f"costs.{cost_key} 必须为数值",
                            source,
                            record_id,
                            f"costs.{cost_key}",
                        )
                    )

    tags_mode = record.get("tags_mode")
    if tags_mode is not None:
        mode = str(tags_mode).strip().lower()
        if mode not in {"normal", "global", "reverse_global"}:
            issues.append(
                ValidationIssue(
                    "error",
                    "tags_mode 必须为 normal/global/reverse_global",
                    source,
                    record_id,
                    "tags_mode",
                )
            )

    mutex_by_tag = record.get("mutex_by_tag")
    if mutex_by_tag is not None and not isinstance(mutex_by_tag, bool):
        issues.append(ValidationIssue("error", "mutex_by_tag 必须为布尔值", source, record_id, "mutex_by_tag"))

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

    permanent_attr_delta = record.get("permanent_attr_delta")
    if permanent_attr_delta is not None:
        if not isinstance(permanent_attr_delta, dict):
            issues.append(ValidationIssue("error", "permanent_attr_delta 必须是字典", source, record_id, "permanent_attr_delta"))
        else:
            for akey, aval in permanent_attr_delta.items():
                if not str(akey).strip():
                    issues.append(ValidationIssue("error", "permanent_attr_delta 包含空键名", source, record_id, "permanent_attr_delta"))
                    continue
                if not _is_number_like(aval):
                    issues.append(
                        ValidationIssue(
                            "error",
                            f"permanent_attr_delta.{akey} 必须为数值",
                            source,
                            record_id,
                            f"permanent_attr_delta.{akey}",
                        )
                    )

    known_keys = {
        "id", "name", "desc", "description",
        "name_i18n_key", "desc_i18n_key", "description_i18n_key",
        "icon_base64",
        "cooldown_s", "duration_s", "mutex", "guaranteed", "random_pools",
        "requires_item", "requires_no_item",
        "costs", "tags_mode", "mutex_by_tag",
        # 条件与标签系统（Phase 1）
        "requires_buff", "requires_no_buff",
        "tags", "fail_messages",
        "_classes",
        # 等级/经验联动（Phase 4）
        "exp", "min_level",
    }
    for key in record:
        if key not in known_keys:
            issues.append(ValidationIssue("warn", "未识别字段", source, record_id, key))

    # min_level 合法性
    if "min_level" in record and (not isinstance(record["min_level"], int) or record["min_level"] < 0):
        issues.append(ValidationIssue("error", "min_level 必须为非负整数", source, record_id, "min_level"))
    if "exp" in record and not _is_number_like(record["exp"]):
        issues.append(ValidationIssue("error", "exp 必须为数值", source, record_id, "exp"))

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
        "icon_base64",
        "guaranteed", "random_pools", "effects", "permanent_attr_delta",
        # 等级/经验联动（Phase 4）
        "exp", "min_level", "clear_buffs",
    }
    for key in record:
        if key not in known_keys:
            issues.append(ValidationIssue("warn", "未识别字段", source, record_id, key))

    if "min_level" in record and (not isinstance(record["min_level"], int) or record["min_level"] < 0):
        issues.append(ValidationIssue("error", "min_level 必须为非负整数", source, record_id, "min_level"))
    if "exp" in record and not _is_number_like(record["exp"]):
        issues.append(ValidationIssue("error", "exp 必须为数值", source, record_id, "exp"))

    return issues


def validate_passive_buff_record(
    record: dict[str, Any],
    source: str,
) -> list[ValidationIssue]:
    """校验被动 buff 触发器记录（module/life/passive_buff/ 目录）。"""
    issues: list[ValidationIssue] = []
    record_id = str(record.get("id") or record.get("name") or "<unknown>")

    if "id" not in record or not str(record.get("id", "")).strip():
        issues.append(ValidationIssue("error", "passive_buff 缺少 id", source, record_id, "id"))

    base_chance = record.get("base_chance")
    if base_chance is not None and not _is_number_like(base_chance):
        issues.append(ValidationIssue("error", "base_chance 必须为数值", source, record_id, "base_chance"))

    attr_bonus = record.get("attr_bonus")
    if attr_bonus is not None and not isinstance(attr_bonus, dict):
        issues.append(ValidationIssue("error", "attr_bonus 必须是字典", source, record_id, "attr_bonus"))

    attr_conditions = record.get("attr_conditions")
    if attr_conditions is not None:
        if not isinstance(attr_conditions, list):
            issues.append(ValidationIssue("error", "attr_conditions 必须是列表", source, record_id, "attr_conditions"))
        else:
            for i, cond in enumerate(attr_conditions):
                if not isinstance(cond, dict):
                    issues.append(ValidationIssue("error", f"attr_conditions[{i}] 必须是字典", source, record_id, f"attr_conditions[{i}]"))
                    continue
                if "attr" not in cond or not str(cond.get("attr", "")).strip():
                    issues.append(ValidationIssue("error", f"attr_conditions[{i}] 缺少 attr", source, record_id, f"attr_conditions[{i}].attr"))
                for k in ("min", "max"):
                    if k in cond and not _is_number_like(cond[k]):
                        issues.append(ValidationIssue("error", f"attr_conditions[{i}].{k} 必须为数值", source, record_id, f"attr_conditions[{i}].{k}"))

    on_trigger = record.get("on_trigger")
    if on_trigger is not None and not isinstance(on_trigger, dict):
        issues.append(ValidationIssue("error", "on_trigger 必须是字典", source, record_id, "on_trigger"))
    elif isinstance(on_trigger, dict):
        duration_formula = on_trigger.get("duration_formula")
        if duration_formula is not None:
            if not isinstance(duration_formula, dict):
                issues.append(
                    ValidationIssue(
                        "error",
                        "on_trigger.duration_formula 必须是字典",
                        source,
                        record_id,
                        "on_trigger.duration_formula",
                    )
                )
            else:
                for fkey in ("base", "min", "max"):
                    fval = duration_formula.get(fkey)
                    if fval is not None and not _is_number_like(fval):
                        issues.append(
                            ValidationIssue(
                                "error",
                                f"on_trigger.duration_formula.{fkey} 必须为数值",
                                source,
                                record_id,
                                f"on_trigger.duration_formula.{fkey}",
                            )
                        )
                terms = duration_formula.get("terms")
                if terms is not None:
                    if not isinstance(terms, list):
                        issues.append(
                            ValidationIssue(
                                "error",
                                "on_trigger.duration_formula.terms 必须是列表",
                                source,
                                record_id,
                                "on_trigger.duration_formula.terms",
                            )
                        )
                    else:
                        for i, term in enumerate(terms):
                            tpath = f"on_trigger.duration_formula.terms[{i}]"
                            if not isinstance(term, dict):
                                issues.append(ValidationIssue("error", f"{tpath} 必须是字典", source, record_id, tpath))
                                continue
                            if not str(term.get("attr") or "").strip():
                                issues.append(
                                    ValidationIssue("error", f"{tpath}.attr 不能为空", source, record_id, f"{tpath}.attr")
                                )
                            coeff = term.get("coeff")
                            if coeff is None or not _is_number_like(coeff):
                                issues.append(
                                    ValidationIssue("error", f"{tpath}.coeff 必须为数值", source, record_id, f"{tpath}.coeff")
                                )

    known_keys = {
        "id", "name",
        "base_chance", "attr_bonus", "attr_conditions",
        "requires_buff", "requires_no_buff",
        "on_trigger",
    }
    for key in record:
        if key not in known_keys:
            issues.append(ValidationIssue("warn", "未识别字段", source, record_id, key))

    return issues


def validate_attr_record(
    record: dict[str, Any],
    source: str,
) -> list[ValidationIssue]:
    """校验属性定义记录（module/life/attrs/ 目录）。"""
    issues: list[ValidationIssue] = []
    record_id = str(record.get("id") or record.get("name") or "<unknown>")

    if "id" not in record or not str(record.get("id", "")).strip():
        issues.append(ValidationIssue("error", "attr 缺少 id", source, record_id, "id"))
    if "name" not in record:
        issues.append(ValidationIssue("warn", "attr 缺少 name", source, record_id, "name"))

    initial = record.get("initial")
    if initial is not None and not _is_number_like(initial):
        issues.append(ValidationIssue("error", "initial 必须为数值", source, record_id, "initial"))

    color = record.get("color")
    if color is not None and not isinstance(color, str):
        issues.append(ValidationIssue("error", "color 必须是字符串（如 #e06c75）", source, record_id, "color"))

    order = record.get("order")
    if order is not None and not isinstance(order, int):
        issues.append(ValidationIssue("warn", "order 建议为整数", source, record_id, "order"))

    # level_table 校验（每属性经验/等级表，可选）
    level_table = record.get("level_table")
    if level_table is not None:
        if not isinstance(level_table, list):
            issues.append(ValidationIssue("error", "level_table 必须是列表", source, record_id, "level_table"))
        else:
            for i, lt in enumerate(level_table):
                if not isinstance(lt, dict):
                    issues.append(ValidationIssue("error", f"level_table[{i}] 必须是字典", source, record_id, f"level_table[{i}]"))
                    continue
                if not isinstance(lt.get("level"), int):
                    issues.append(ValidationIssue("error", f"level_table[{i}].level 必须是整数", source, record_id, f"level_table[{i}].level"))
                if not _is_number_like(lt.get("exp_required")):
                    issues.append(ValidationIssue("error", f"level_table[{i}].exp_required 必须为数值", source, record_id, f"level_table[{i}].exp_required"))
                pb = lt.get("permanent_bonus")
                if pb is not None and not isinstance(pb, dict):
                    issues.append(ValidationIssue("error", f"level_table[{i}].permanent_bonus 必须是字典", source, record_id, f"level_table[{i}].permanent_bonus"))

    # char_level_bonuses 校验（全局等级驱动的属性加成，可选）
    char_level_bonuses = record.get("char_level_bonuses")
    if char_level_bonuses is not None:
        if not isinstance(char_level_bonuses, list):
            issues.append(ValidationIssue("error", "char_level_bonuses 必须是列表", source, record_id, "char_level_bonuses"))
        else:
            for i, bonus in enumerate(char_level_bonuses):
                if not isinstance(bonus, dict):
                    issues.append(ValidationIssue("error", f"char_level_bonuses[{i}] 必须是字典", source, record_id, f"char_level_bonuses[{i}]"))
                    continue
                b_type = str(bonus.get("type") or "").strip()
                if b_type not in ("at_level", "per_levels"):
                    issues.append(ValidationIssue("error", f"char_level_bonuses[{i}].type 必须为 'at_level' 或 'per_levels'", source, record_id, f"char_level_bonuses[{i}].type"))
                if b_type == "at_level":
                    if not isinstance(bonus.get("level"), int):
                        issues.append(ValidationIssue("error", f"char_level_bonuses[{i}].level 必须是正整数", source, record_id, f"char_level_bonuses[{i}].level"))
                elif b_type == "per_levels":
                    if not isinstance(bonus.get("every"), int) or int(bonus.get("every", 0)) <= 0:
                        issues.append(ValidationIssue("error", f"char_level_bonuses[{i}].every 必须是正整数", source, record_id, f"char_level_bonuses[{i}].every"))
                    offset = bonus.get("min_level_offset")
                    if offset is not None and not isinstance(offset, int):
                        issues.append(ValidationIssue("warn", f"char_level_bonuses[{i}].min_level_offset 建议为整数", source, record_id, f"char_level_bonuses[{i}].min_level_offset"))
                b_bonus = bonus.get("bonus")
                if b_bonus is not None and not isinstance(b_bonus, dict):
                    issues.append(ValidationIssue("error", f"char_level_bonuses[{i}].bonus 必须是字典", source, record_id, f"char_level_bonuses[{i}].bonus"))

    known_keys = {
        "id", "name", "i18n_key", "color", "initial", "order",
        "desc", "description", "desc_i18n_key", "description_i18n_key",
        "level_table", "char_level_bonuses",
    }
    for key in record:
        if key not in known_keys:
            issues.append(ValidationIssue("warn", "未识别字段", source, record_id, key))

    return issues


def validate_level_config(
    data: dict[str, Any],
    source: str = "level_setting.json",
) -> list[ValidationIssue]:
    """校验全局等级配置文件（module/life/level/level_setting.json）。"""
    issues: list[ValidationIssue] = []
    record_id = "level_config"

    init_exp = data.get("initial_exp_required")
    if not _is_number_like(init_exp) or float(init_exp) <= 0:
        issues.append(ValidationIssue("error", "initial_exp_required 必须为正数", source, record_id, "initial_exp_required"))

    passive_exp = data.get("passive_exp_per_tick")
    if passive_exp is not None:
        if not _is_number_like(passive_exp) or float(passive_exp) < 0:
            issues.append(ValidationIssue("error", "passive_exp_per_tick 必须为非负数", source, record_id, "passive_exp_per_tick"))

    growth_ranges = data.get("growth_ranges")
    if growth_ranges is None or not isinstance(growth_ranges, list) or len(growth_ranges) == 0:
        issues.append(ValidationIssue("error", "growth_ranges 必须是非空列表", source, record_id, "growth_ranges"))
        return issues

    max_to_level = 0
    current_exp = float(init_exp) if _is_number_like(init_exp) else 100.0
    for i, rng in enumerate(growth_ranges):
        if not isinstance(rng, dict):
            issues.append(ValidationIssue("error", f"growth_ranges[{i}] 必须是字典", source, record_id, f"growth_ranges[{i}]"))
            continue
        fl = rng.get("from_level")
        tl = rng.get("to_level")
        eg = rng.get("exp_growth")
        if not isinstance(fl, int) or fl < 1:
            issues.append(ValidationIssue("error", f"growth_ranges[{i}].from_level 必须是 ≥1 的整数", source, record_id, f"growth_ranges[{i}].from_level"))
        if not isinstance(tl, int) or (isinstance(fl, int) and tl < fl):
            issues.append(ValidationIssue("error", f"growth_ranges[{i}].to_level 必须是 ≥from_level 的整数", source, record_id, f"growth_ranges[{i}].to_level"))
        if not _is_number_like(eg):
            issues.append(ValidationIssue("error", f"growth_ranges[{i}].exp_growth 必须为数值", source, record_id, f"growth_ranges[{i}].exp_growth"))
            continue
        # 验证该区间内任意等级的升级经验不会 ≤ 0
        if isinstance(fl, int) and isinstance(tl, int):
            check_exp = current_exp
            for level in range(fl, tl + 1):
                if level > fl:
                    check_exp += float(eg)
                if check_exp <= 0:
                    issues.append(ValidationIssue("warn", f"growth_ranges[{i}] 中第 {level} 级升级所需经验 ≤0，请检查 exp_growth", source, record_id, f"growth_ranges[{i}]"))
                    break
            current_exp = check_exp + float(eg)
            max_to_level = tl

    known_keys = {"initial_exp_required", "passive_exp_per_tick", "growth_ranges"}
    for key in data:
        if key not in known_keys:
            issues.append(ValidationIssue("warn", "未识别字段", source, record_id, key))

    return issues


def validate_tag_record(
    record: dict[str, Any],
    source: str,
) -> list[ValidationIssue]:
    """校验标签定义记录（module/life/tags/ 目录）。"""
    issues: list[ValidationIssue] = []
    record_id = str(record.get("id") or "<unknown>")

    if "id" not in record or not str(record.get("id", "")).strip():
        issues.append(ValidationIssue("error", "tag 缺少 id", source, record_id, "id"))
    if "buff_id" not in record or not str(record.get("buff_id", "")).strip():
        issues.append(ValidationIssue("warn", "tag 缺少 buff_id", source, record_id, "buff_id"))

    global_event = record.get("global_event")
    if global_event is not None and not isinstance(global_event, bool):
        issues.append(ValidationIssue("error", "global_event 必须是布尔值", source, record_id, "global_event"))

    known_keys = {
        "id", "buff_id", "name", "i18n_key", "color",
        "use_restricted_i18n_key", "fire_restricted_i18n_key",
        "global_event",
    }
    for key in record:
        if key not in known_keys:
            issues.append(ValidationIssue("warn", "未识别字段", source, record_id, key))

    return issues


def validate_state_record(
    record: dict[str, Any],
    source: str,
) -> list[ValidationIssue]:
    """校验状态定义记录（module/life/status/ 目录）。"""
    issues: list[ValidationIssue] = []
    record_id = str(record.get("id") or record.get("name") or "<unknown>")

    if "id" not in record or not str(record.get("id", "")).strip():
        issues.append(ValidationIssue("error", "state 缺少 id", source, record_id, "id"))
    if "name" not in record:
        issues.append(ValidationIssue("warn", "state 缺少 name", source, record_id, "name"))
    for str_field in ("i18n_key",):
        if str_field in record and not isinstance(record[str_field], str):
            issues.append(ValidationIssue("error", f"{str_field} 必须是字符串", source, record_id, str_field))
    for num_field in ("default", "min", "max"):
        if num_field in record and not _is_number_like(record[num_field]):
            issues.append(ValidationIssue("warn", f"{num_field} 建议为数值", source, record_id, num_field))
    if "order" in record and not isinstance(record["order"], int):
        issues.append(ValidationIssue("warn", "order 建议为整数", source, record_id, "order"))

    effects = record.get("effects")
    if effects is not None:
        if not isinstance(effects, list):
            issues.append(ValidationIssue("error", "effects 必须是列表", source, record_id, "effects"))
        else:
            for ei, effect in enumerate(effects):
                if not isinstance(effect, dict):
                    issues.append(ValidationIssue("error", f"effects[{ei}] 必须是字典", source, record_id, f"effects[{ei}]"))
                    continue
                for cond_key in ("requires_buff", "requires_no_buff"):
                    if cond_key in effect and not isinstance(effect[cond_key], (str, list)):
                        issues.append(ValidationIssue("warn", f"effects[{ei}].{cond_key} 应为字符串或字符串列表", source, record_id, f"effects[{ei}].{cond_key}"))

    known_keys = {
        "id", "name", "i18n_key", "default", "min", "max", "order", "effects",
    }
    for key in record:
        if key not in known_keys:
            issues.append(ValidationIssue("warn", "未识别字段", source, record_id, key))

    return issues


def validate_nutrition_record(
    record: dict[str, Any],
    source: str,
) -> list[ValidationIssue]:
    """校验营养定义记录（module/life/nutrition/ 目录）。"""
    issues: list[ValidationIssue] = []
    record_id = str(record.get("id") or record.get("name") or "<unknown>")

    if "id" not in record or not str(record.get("id", "")).strip():
        issues.append(ValidationIssue("error", "nutrition 缺少 id", source, record_id, "id"))
    if "name" not in record:
        issues.append(ValidationIssue("warn", "nutrition 缺少 name", source, record_id, "name"))
    for str_field in ("i18n_key",):
        if str_field in record and not isinstance(record[str_field], str):
            issues.append(ValidationIssue("error", f"{str_field} 必须是字符串", source, record_id, str_field))
    for num_field in ("default", "min", "max", "decay"):
        if num_field in record and not _is_number_like(record[num_field]):
            issues.append(ValidationIssue("warn", f"{num_field} 建议为数值", source, record_id, num_field))
    if "order" in record and not isinstance(record["order"], int):
        issues.append(ValidationIssue("warn", "order 建议为整数", source, record_id, "order"))

    effects = record.get("effects")
    if effects is not None:
        if not isinstance(effects, list):
            issues.append(ValidationIssue("error", "effects 必须是列表", source, record_id, "effects"))
        else:
            for ei, effect in enumerate(effects):
                if not isinstance(effect, dict):
                    issues.append(ValidationIssue("error", f"effects[{ei}] 必须是字典", source, record_id, f"effects[{ei}]"))
                    continue
                for cond_key in ("requires_buff", "requires_no_buff"):
                    if cond_key in effect and not isinstance(effect[cond_key], (str, list)):
                        issues.append(ValidationIssue("warn", f"effects[{ei}].{cond_key} 应为字符串或字符串列表", source, record_id, f"effects[{ei}].{cond_key}"))

    known_keys = {
        "id", "name", "i18n_key", "default", "min", "max", "order", "decay", "effects",
    }
    for key in record:
        if key not in known_keys:
            issues.append(ValidationIssue("warn", "未识别字段", source, record_id, key))

    return issues

