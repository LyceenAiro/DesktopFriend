# attrs 目录

此目录存放**属性（Attribute）定义**，属性是影响宠物各方面能力的基础数值。

## JSON 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一属性 ID |
| `name` | string | 可读属性名称 |
| `i18n_key` | string | 国际化翻译键 |
| `color` | string | 属性在 UI 中的颜色（十六进制） |
| `initial` | number | 初始属性值 |
| `order` | number | 在 UI 中的排列顺序 |
| `char_level_bonuses` | list\<dict\> | 升级时获得的属性加成规则（可选） |

## 属性加成规则 (char_level_bonuses)

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | string | 加成类型，通常为 `"per_levels"` |
| `every` | number | 每 N 级获得一次加成 |
| `bonus` | dict | 单次加成的属性值，如 `{"vit": 1}` |
| `min_level_offset` | number | 最小等级偏移（从第几级开始） |

## 示例

```json
[
  {
    "id": "vit",
    "name": "体质",
    "i18n_key": "life.attr.vit",
    "color": "#e06c75",
    "initial": 5,
    "order": 10,
    "char_level_bonuses": [
      {"type": "per_levels", "every": 5, "bonus": {"vit": 1}, "min_level_offset": 0}
    ]
  },
  {
    "id": "str",
    "name": "力量",
    "i18n_key": "life.attr.str",
    "color": "#d4834a",
    "initial": 3,
    "order": 20,
    "char_level_bonuses": [
      {"type": "per_levels", "every": 10, "bonus": {"str": 1}, "min_level_offset": 0}
    ]
  }
]
```

## 使用建议

- 属性 ID 应为英文小写，便于代码引用
- 属性值的初始值应根据游戏平衡性设计
- 使用 `i18n_key` 实现多语言支持（对应 `lang/zh_cn.json` 等文件）
- 升级加成应该递进式增长，后期属性更容易获得提升
