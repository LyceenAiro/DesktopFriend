# item 目录

此目录存放**物品定义**，定义宠物可以拥有和使用的各种物品。

## 目录结构

- `foods/` - 食物物品（对营养系统有效）
- `consumables/` - 消耗品（一次性使用）
- `defaultItem/` - 默认物品（初始赠送）

## JSON 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一物品 ID |
| `name` | string | 可读物品名称 |
| `name_i18n_key` | string | 名称国际化键 |
| `desc` | string | 物品描述 |
| `desc_i18n_key` | string | 描述国际化键 |
| `usable` | bool | 物品是否可以使用/消耗 |
| `exp` | number | 使用该物品获得的经验值 |
| `nutrition` | dict | 营养效果，如 `{"satiety_meter": 2000, "hydration": 500}` |
| `effects` | dict | 直接效果，如 `{"happy": 20, "hp": 50}` |
| `buffs` | list\<dict\> | 使用时获得的 buff（可选） |
| `outcomes` | list\<dict\> | 使用时触发的事件结果（可选） |
| `category` | string | 物品分类（可选） |
| `rarity` | string | 稀有度（可选） |

## 示例

```json
[
  {
    "id": "water",
    "name": "饮用水",
    "name_i18n_key": "life.item.water.name",
    "desc": "基础补给品，补充大量水分并获得少量经验。",
    "desc_i18n_key": "life.item.water.desc",
    "usable": true,
    "exp": 1,
    "nutrition": {
      "hydration": 1000
    }
  },
  {
    "id": "food",
    "name": "食物",
    "name_i18n_key": "life.item.food.name",
    "desc": "基础食物，补充饱腹并获得少量经验。",
    "desc_i18n_key": "life.item.food.desc",
    "usable": true,
    "exp": 1,
    "nutrition": {
      "satiety_meter": 2000
    }
  },
  {
    "id": "medicine",
    "name": "药物",
    "name_i18n_key": "life.item.medicine.name",
    "desc": "恢复药物，可以治疗伤害和某些状态。",
    "desc_i18n_key": "life.item.medicine.desc",
    "usable": true,
    "exp": 2,
    "effects": {
      "hp": 100,
      "happy": 10
    },
    "buffs": [
      {"id": "healed", "duration": 30}
    ]
  },
  {
    "id": "special_potion",
    "name": "特殊药水",
    "name_i18n_key": "life.item.special_potion.name",
    "desc": "稀有的魔法药水，具有神秘的效果。",
    "desc_i18n_key": "life.item.special_potion.desc",
    "usable": true,
    "exp": 5,
    "outcomes": [
      {
        "id": "mysterious_effect"
      }
    ],
    "rarity": "rare"
  }
]
```

## 使用建议

- 食物物品应该优先使用 `nutrition` 字段，而非 `effects`
- 药物物品应该使用 `effects` 或 `buffs` 来恢复状态
- `usable` 为 false 的物品是收集品或装饰品，不能直接使用
- `exp` 应该根据物品的稀有度和效用来设置
- 分类存放不同类型的物品，便于逻辑处理和 UI 展示
- 物品描述应该清晰说明其效果，帮助玩家做出决策
- 使用 `outcomes` 创建随机结果的物品，增加期待感

## 物品使用流程

1. 玩家在背包中选择物品
2. 系统检查 `usable` 是否为 true
3. 应用 `effects`、`nutrition`、`buffs` 等效果
4. 如果有 `outcomes`，随机触发其中一个
5. 获得 `exp` 经验值
6. 从背包中减少一件
7. 刷新 UI 显示
