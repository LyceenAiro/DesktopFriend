# nutrition 目录

此目录存放**营养系统定义**，营养代表宠物的饮食指标（饱腹度、水分等），会随时间衰减。

## JSON 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一营养指标 ID |
| `name` | string | 可读营养名称 |
| `i18n_key` | string | 国际化翻译键 |
| `default` | number | 默认初始值 |
| `min` | number | 最小值（下界） |
| `max` | number | 最大值（上界） |
| `order` | number | 在 UI 中的排列顺序 |
| `decay` | number | 每 tick 衰减量 |
| `effects` | list\<dict\> | 营养值范围触发的 buff 效果（可选） |

## 效果规则 (effects)

| 字段 | 类型 | 说明 |
|---|---|---|
| `min` | number | 触发效果的最小营养值 |
| `max` | number | 触发效果的最大营养值 |
| `buff_id` | string | 当营养值在此范围内时自动应用的 buff ID |

## 示例

```json
[
  {
    "id": "satiety_meter",
    "name": "饱腹",
    "i18n_key": "life.nutrition.satiety_meter",
    "default": 3900,
    "min": 0,
    "max": 6000,
    "order": 10,
    "decay": 0.2,
    "effects": [
      {
        "min": 5500,
        "max": 6001,
        "buff_id": "well_fed"
      },
      {
        "min": 1500,
        "max": 5500,
        "buff_id": "full"
      },
      {
        "min": 0,
        "max": 1500,
        "buff_id": "hungry"
      },
      {
        "min": 0,
        "max": 0,
        "buff_id": "starving"
      }
    ]
  },
  {
    "id": "hydration",
    "name": "水分",
    "i18n_key": "life.nutrition.hydration",
    "default": 3900,
    "min": 0,
    "max": 6000,
    "order": 20,
    "decay": 0.15,
    "effects": [
      {
        "min": 0,
        "max": 1000,
        "buff_id": "dehydrated"
      }
    ]
  }
]
```

## 使用建议

- 营养指标会在每个 tick 衰减，`decay` 值应该合理设置
- 使用分级的 `effects` 规则来创建多个状态阶段（如：吃饱、正常、饥饿、濒死）
- 营养值的最大值应该根据衰减速度和补充效率来平衡
- 不同营养指标的衰减速度可以不同，模拟真实的生理需求差异
