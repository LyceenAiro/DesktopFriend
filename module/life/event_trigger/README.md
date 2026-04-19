# event_trigger 目录

此目录存放**事件触发器定义**，定义玩家可以手动触发的事件及其效果。

## 目录结构

- `daily/` - 日常活动事件（睡觉、运动、探险等）
- `outdoor/` - 户外活动事件（探索、冒险等）

## JSON 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一触发器 ID |
| `name` | string | 可读事件名称 |
| `name_i18n_key` | string | 名称国际化键 |
| `desc` | string | 事件描述 |
| `desc_i18n_key` | string | 描述国际化键 |
| `cooldown_s` | number | 冷却时间（秒），触发后需等待才能再次触发 |
| `cost` | dict | 触发该事件所需的状态/资源消耗（可选） |
| `tags_mode` | string | 标签限制模式（可选） |
| `tags` | list\<string\> | 适用的标签列表（可选） |
| `guaranteed` | dict | 必然获得的奖励 |
| `random_pools` | list\<dict\> | 随机奖励池 |

## 标签模式 (tags_mode)

| 值 | 说明 |
|---|---|
| `"require"` | 必须存在列表中的任意标签才能触发 |
| `"forbid"` | 存在列表中的任意标签时禁止触发 |
| `"reverse_global"` | 全局标签的反向限制（如不在某些全局状态中） |

## 奖励结构

参考 `event_outcome/` 中的说明，`guaranteed` 和 `random_pools` 的结构相同。

## 示例

```json
[
  {
    "id": "sleep_action",
    "name": "睡觉",
    "name_i18n_key": "life.trigger.sleep_action.name",
    "desc": "尝试进入睡眠恢复状态。",
    "desc_i18n_key": "life.trigger.sleep_action.desc",
    "cooldown_s": 120,
    "cost": {
      "energy": 100
    },
    "tags_mode": "reverse_global",
    "guaranteed": {
      "items": [],
      "buffs": [],
      "outcomes": []
    },
    "random_pools": [
      {
        "entries": [
          {"type": "outcome", "id": "sleep_insomnia", "chance": 10, "flat_bonus": -20, "state_bonus": {"psc": 0.1}}
        ],
        "fallback": {"type": "outcome", "id": "sleep_success"}
      }
    ]
  },
  {
    "id": "exercise",
    "name": "锻炼",
    "name_i18n_key": "life.trigger.exercise.name",
    "desc": "进行体能锻炼，提升体质并消耗能量。",
    "desc_i18n_key": "life.trigger.exercise.desc",
    "cooldown_s": 300,
    "cost": {
      "energy": 200,
      "happy": 50
    },
    "guaranteed": {
      "items": [],
      "buffs": [],
      "outcomes": []
    },
    "random_pools": [
      {
        "entries": [
          {"type": "outcome", "id": "exercise_success", "chance": 80},
          {"type": "outcome", "id": "exercise_injury", "chance": 20}
        ]
      }
    ]
  }
]
```

## 使用建议

- `cooldown_s` 防止玩家过度滥用某个事件
- `cost` 字段用来消耗宠物的资源，制造决策压力
- 随机池应该包含成功和失败的结果，增加游戏张力
- 使用标签系统限制某些事件的触发条件（如睡眠状态下不能睡觉）
- 事件名称应该简洁明了，让玩家快速理解
- 分类存放不同类型的事件，便于管理和扩展

## 触发流程

1. 玩家点击事件按钮
2. 系统检查冷却时间、标签、成本
3. 如果所有条件满足，扣除成本
4. 随机生成结果（先 `random_pools`，无中选则 `fallback`，再加上 `guaranteed`）
5. 应用结果（状态变化、获得物品、获得 buff）
6. 刷新 UI 显示
