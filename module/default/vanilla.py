from __future__ import annotations

from module.default.action import ActionSystem


def register_vanilla_actions(action_system: ActionSystem, pet_art_list: list, art_constants: dict | None = None) -> None:
    """将原版硬编码动画注册为 action_system 中的动作。

    Args:
        action_system: ActionSystem 实例
        pet_art_list: PetArtList（全局图像列表）
        art_constants: 可选的常量映射，若为 None 则从 ui.PetArt 导入
    """
    if art_constants is None:
        from ui.PetArt import (
            DEFAULT, DEFAULT2, JUMP, PICKUP,
            WALK1, WALK2, WALK3, WALK4,
            WALK1_R, WALK2_R, WALK3_R, WALK4_R,
            NONE_ART,
        )
        C = {
            "DEFAULT": DEFAULT, "DEFAULT2": DEFAULT2,
            "JUMP": JUMP, "PICKUP": PICKUP,
            "WALK1": WALK1, "WALK2": WALK2, "WALK3": WALK3, "WALK4": WALK4,
            "WALK1_R": WALK1_R, "WALK2_R": WALK2_R, "WALK3_R": WALK3_R, "WALK4_R": WALK4_R,
            "NONE_ART": NONE_ART,
        }
    else:
        C = art_constants

    # 待机动画（loop，normal 模式）
    action_system.register_vanilla_action(
        "vanilla.idle",
        frames=[pet_art_list[C["DEFAULT"]], pet_art_list[C["DEFAULT2"]]],
        frame_interval_ms=action_system._default_interval_ms,
        play_mode="loop",
        block_mode="normal",
    )

    # 拖拽动画（once，exclusive 模式）
    action_system.register_vanilla_action(
        "vanilla.drag",
        frames=[pet_art_list[C["PICKUP"]]],
        frame_interval_ms=0,
        play_mode="once",
        block_mode="exclusive",
    )

    # 行走动画 - 左（loop，exclusive 模式）
    action_system.register_vanilla_action(
        "vanilla.walk_left",
        frames=[pet_art_list[C["WALK1"]], pet_art_list[C["WALK2"]],
                pet_art_list[C["WALK3"]], pet_art_list[C["WALK4"]]],
        frame_interval_ms=150,
        play_mode="loop",
        block_mode="exclusive",
    )

    # 行走动画 - 右（loop，exclusive 模式）
    action_system.register_vanilla_action(
        "vanilla.walk_right",
        frames=[pet_art_list[C["WALK1_R"]], pet_art_list[C["WALK2_R"]],
                pet_art_list[C["WALK3_R"]], pet_art_list[C["WALK4_R"]]],
        frame_interval_ms=150,
        play_mode="loop",
        block_mode="exclusive",
    )

    # 跳跃动画（once，exclusive 模式）
    action_system.register_vanilla_action(
        "vanilla.jump",
        frames=[pet_art_list[C["JUMP"]]],
        frame_interval_ms=150,
        play_mode="once",
        block_mode="exclusive",
    )

    # 隐藏动画（once，exclusive 模式）
    action_system.register_vanilla_action(
        "vanilla.hide",
        frames=[pet_art_list[C["NONE_ART"]]],
        frame_interval_ms=0,
        play_mode="once",
        block_mode="exclusive",
    )
