# event_outcome 目录

此目录存放**事件结果定义**，定义事件触发或被动 buff 触发时可能产生的各种结果。

## JSON 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一结果 ID |
| `name` | string | 可读结果名称 |
| `name_i18n_key` | string | 名称国际化键 |
| `desc` | string | 结果描述 |
| `desc_i18n_key` | string | 描述国际化键 |
| `effects` | dict | 直接应用的效果，如 `{"happy": 10, "hp": -5}` |
| `guaranteed` | dict | 必然获得的奖励（物品、buff、后续结果） |
| `random_pools` | list\<dict\> | 随机抽取的奖励池（可选） |
| `tag_id` | string | 事件标签（可选） |

## 必然奖励 (guaranteed)

| 字段 | 类型 | 说明 |
|---|---|---|
| `items` | list\<dict\> | 物品列表：`[{"id": "food", "count": 1}]` |
| `buffs` | list\<dict\> | buff 列表：`[{"id": "sleep", "duration": 60}]` |
| `outcomes` | list\<dict\> | 后续结果：`[{"id": "secondary_outcome"}]` |

## 随机奖励池 (random_pools)

| 字段 | 类型 | 说明 |
|---|---|---|
| `entries` | list\<dict\> | 随机条目列表 |
| `fallback` | dict | 当所有条目概率都不中时的备选结果 |

### 随机条目字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | string | 奖励类型：`"item"`, `"buff"`, `"outcome"` |
| `id` | string | 对应的物品/buff/结果 ID |
| `chance` | number | 基础概率（百分比，0-100） |
| `flat_bonus` | number | 概率固定加值 |
| `state_bonus` | dict | 根据状态值的概率调整，如 `{"psc": 0.1}` 每 1 点精神加 0.1% |
| `attr_bonus` | dict | 根据属性值的概率调整 |
| `count` | number | 物品数量（仅 item 类型） |

## 示例

```json
[
  {
    "id": "wild_find_water",
    "name": "找到饮用水",
    "name_i18n_key": "life.outcome.wild_find_water.name",
    "desc": "探索中发现可饮用水源。",
    "desc_i18n_key": "life.outcome.wild_find_water.desc",
    "effects": {"happy": 10},
    "guaranteed": {
      "items": [{"id": "water", "count": 2}],
      "buffs": [],
      "outcomes": []
    },
    "random_pools": [
      {
        "entries": [
          {"type": "item", "id": "water", "count": 1, "chance": 50}
        ]
      }
    ]
  },
  {
    "id": "explore_danger",
    "name": "遭遇危险",
    "name_i18n_key": "life.outcome.explore_danger.name",
    "desc": "探索中意外遭遇危险。",
    "desc_i18n_key": "life.outcome.explore_danger.desc",
    "effects": {"hp": -50, "happy": -20},
    "guaranteed": {
      "items": [],
      "buffs": [],
      "outcomes": []
    },
    "random_pools": [
      {
        "entries": [
          {"type": "item", "id": "medicine", "count": 1, "chance": 30}
        ],
        "fallback": {"type": "outcome", "id": "injured"}
      }
    ]
  }
]
```

## 使用建议

- 概率调整通常结合属性值或状态值，模拟宠物的成长影响
- 使用 `fallback` 确保随机池始终有结果，避免"无事发生"
- 后续结果可以链式触发，实现复杂的事件流
- `effects` 直接修改状态值，是最即时的反馈
- 分类存放不同类型的结果（如 `starter_outcomes.json` 放初始赠送结果）
