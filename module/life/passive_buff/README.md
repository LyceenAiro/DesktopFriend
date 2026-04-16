# passive_buff 目录

此目录存放**被动 buff 触发器**定义，每 tick 按条件和概率自动检测并激活。

## JSON 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一 ID |
| `name` | string | 可读名称（可选） |
| `base_chance` | number | 每 tick 基础触发概率（%），建议设置较小值（如 0.1~2） |
| `requires_buff` | string\|list | 存在列表中任意 buff 才检测本条目（可选） |
| `requires_no_buff` | string\|list | 存在列表中任意 buff 时跳过本条目（可选） |
| `attr_conditions` | list\<dict\> | 属性值条件，`[{"attr": "vit", "min": 0, "max": 5}]`，全部满足才继续（可选） |
| `attr_bonus` | dict | 属性值影响概率偏移，`{"vit": -0.1}` 表示每 1 点 vit 减少 0.1% 概率（可选） |
| `on_trigger` | dict | 触发时执行的效果，支持 `{"buff_id": "sick"}` 或直接状态/营养效果字段 |

## 示例

```json
[
  {
    "id": "sick_chance",
    "name": "随机生病",
    "base_chance": 0.5,
    "requires_no_buff": ["sick"],
    "attr_conditions": [{"attr": "vit", "max": 5}],
    "attr_bonus": {"vit": -0.1},
    "on_trigger": {"buff_id": "sick"}
  }
]
```
