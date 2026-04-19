# status 目录

此目录存放**状态（Status/State）定义**，状态代表宠物的生存状态指标（HP、心情、体力等）。

## JSON 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一状态 ID |
| `name` | string | 可读状态名称 |
| `i18n_key` | string | 国际化翻译键 |
| `default` | number | 默认初始值 |
| `min` | number | 最小值（下界） |
| `max` | number | 最大值（上界） |
| `order` | number | 在 UI 中的排列顺序 |
| `effects` | list\<dict\> | 状态值范围触发的 buff 效果（可选） |

## 效果规则 (effects)

| 字段 | 类型 | 说明 |
|---|---|---|
| `min` | number | 触发效果的最小状态值 |
| `max` | number | 触发效果的最大状态值 |
| `buff_id` | string | 当状态在此范围内时自动应用的 buff ID |

## 示例

```json
[
  {
    "id": "hp",
    "name": "HP",
    "i18n_key": "life.state.hp",
    "default": 1000,
    "min": 0,
    "max": 1000,
    "order": 10,
    "effects": [
      { "min": 0, "max": 100, "buff_id": "dying" }
    ]
  },
  {
    "id": "happy",
    "name": "HAPPY",
    "i18n_key": "life.state.happy",
    "default": 1000,
    "min": 0,
    "max": 1000,
    "order": 20,
    "effects": [
      { "min": 0, "max": 200, "buff_id": "depressed" }
    ]
  },
  {
    "id": "energy",
    "name": "体力",
    "i18n_key": "life.state.energy",
    "default": 1000,
    "min": 0,
    "max": 1000,
    "order": 30,
    "effects": [
      { "min": 0, "max": 300, "buff_id": "exhausted" }
    ]
  }
]
```

## 使用建议

- 状态值应该有合理的上下界，避免无限增长
- 使用 `effects` 来自动触发相应的负面 buff（如 HP 过低时自动进入"垂死"状态）
- 所有状态应该按 `order` 字段排序，确保 UI 显示的一致性
- `i18n_key` 应该对应 `lang/` 目录中的翻译键
