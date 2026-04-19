# buff 目录

此目录存放**Buff 效果定义**，Buff 是临时的或持久的状态效果，会对宠物的各项指标产生影响。

## 目录结构

- `boost/` - 增益 buff（正向效果）
- `first_aid/` - 急救 buff（特殊治疗效果）
- `nutrition/` - 营养 buff（饮食相关效果）
- `potion/` - 药水 buff（药物效果）
- `status/` - 状态 buff（负面或中立效果）

## JSON 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一 Buff ID |
| `name` | string | 可读 Buff 名称 |
| `name_i18n_key` | string | 名称国际化键（可选） |
| `desc` | string | Buff 描述 |
| `desc_i18n_key` | string | 描述国际化键（可选） |
| `hps` | number | 每 tick HP 变化值 |
| `happys` | number | 每 tick 心情变化值 |
| `energys` | number | 每 tick 体力变化值 |
| `pscs` | number | 每 tick 精神变化值 |
| `hpst` | number | Buff 持续时间（秒），不指定则永久 |
| `hpsr` | string | Buff 刷新模式：`"refresh"` 重置计时器，`"add"` 累计时间 |
| 属性修改 | number/string | 直接属性修改，如 `"vit": -5` 或 `"energy_max": "-40%"` |
| 其他 | various | 其他状态/营养数值修改 |

## 示例

```json
[
  {
    "id": "ill",
    "name": "生病",
    "name_i18n_key": "life.buff.ill.name",
    "desc": "身体不适，持续损耗状态。",
    "desc_i18n_key": "life.buff.ill.desc",
    "hps": -0.5,
    "happys": -0.5,
    "energy_max": "-40%",
    "psc_max": "-40%",
    "hpst": 120,
    "hpsr": "refresh"
  },
  {
    "id": "sleep",
    "name": "睡眠",
    "name_i18n_key": "life.buff.sleep.name",
    "desc": "进入睡眠状态，快速恢复精神与体力。",
    "desc_i18n_key": "life.buff.sleep.desc",
    "hps": 0.01,
    "energys": 2,
    "pscs": 6,
    "happys": 0.2,
    "hpst": 180,
    "hpsr": "refresh"
  },
  {
    "id": "depressed",
    "name": "抑郁",
    "name_i18n_key": "life.buff.depressed.name",
    "desc": "心情低落，体质表现受到压制。",
    "desc_i18n_key": "life.buff.depressed.desc",
    "happys": -0.01,
    "vit": -5
  }
]
```

## 使用建议

- 临时 buff（有 `hpst`）通常用于状态或战斗效果
- 永久 buff（无 `hpst`）通常用于属性修改或特殊效果
- `hpsr: "refresh"` 适合反复触发的 buff，每次触发时重置计时器
- 百分比修改（如 `"energy_max": "-40%"`）用于临时限制能力值上限
- 分类存放不同类型的 buff，便于维护和查找
