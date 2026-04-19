# tags 目录

此目录存放**事件标签定义**，标签用于分类和限制事件的触发条件和可用性。

## JSON 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一标签 ID |
| `name` | string | 可读标签名称 |
| `i18n_key` | string | 名称国际化键 |
| `buff_id` | string | 该标签关联的 buff ID（激活标签时应用的 buff） |
| `color` | string | 标签在 UI 中的颜色（十六进制） |
| `global_event` | bool | 是否为全局事件标签（影响全局状态） |
| `use_restricted_i18n_key` | string | 使用限制提示的国际化键（可选） |
| `fire_restricted_i18n_key` | string | 触发限制提示的国际化键（可选） |

## 标签的作用

- **分类事件**：不同标签代表不同类型的事件（睡眠、饮食、运动等）
- **限制触发**：事件可以声明需要或禁止特定标签
- **全局状态**：全局事件标签会影响所有事件的可用性
- **关联 Buff**：激活标签时自动应用相关 buff

## 示例

```json
[
  {
    "id": "first_aid",
    "name": "急救",
    "i18n_key": "life.tag.first_aid",
    "use_restricted_i18n_key": "life.tag.first_aid.use_restricted",
    "fire_restricted_i18n_key": "life.tag.first_aid.fire_restricted",
    "buff_id": "dying",
    "color": "#e06c75",
    "global_event": true
  },
  {
    "id": "sleep",
    "name": "睡眠",
    "i18n_key": "life.tag.sleep",
    "use_restricted_i18n_key": "life.tag.sleep.use_restricted",
    "fire_restricted_i18n_key": "life.tag.sleep.fire_restricted",
    "buff_id": "sleep",
    "color": "#3d7be0",
    "global_event": true
  },
  {
    "id": "exercise",
    "name": "锻炼",
    "i18n_key": "life.tag.exercise",
    "use_restricted_i18n_key": "life.tag.exercise.use_restricted",
    "fire_restricted_i18n_key": "life.tag.exercise.fire_restricted",
    "buff_id": "exercising",
    "color": "#98c379",
    "global_event": true
  },
  {
    "id": "eating",
    "name": "进食",
    "i18n_key": "life.tag.eating",
    "use_restricted_i18n_key": "life.tag.eating.use_restricted",
    "fire_restricted_i18n_key": "life.tag.eating.fire_restricted",
    "buff_id": "eating",
    "color": "#d4834a",
    "global_event": false
  }
]
```

## 标签在事件系统中的应用

### 事件触发器中的限制

事件可以声明标签模式来限制何时可以触发：

```json
{
  "id": "sleep_action",
  "tags_mode": "reverse_global",
  "tags": ["sleep"],
  // 表示：当全局事件标签不在 ["sleep"] 中时，才能触发睡眠事件
}
```

### 标签模式说明

- `require`：必须存在任意指定标签
- `forbid`：不能存在任意指定标签
- `reverse_global`：全局标签的反向要求（如不在某些全局状态中）

## 使用建议

- `global_event: true` 的标签应该代表互斥的全局状态（如睡眠、运动、进食）
- `global_event: false` 的标签可以用于局部事件分类
- 使用 `color` 在 UI 中直观区分不同标签
- 限制提示信息（`use_restricted_i18n_key`、`fire_restricted_i18n_key`）应该明确说明限制原因
- 关联的 `buff_id` 应该在 `buff/` 目录中定义
- 标签 ID 应该清晰表达其含义，便于事件配置引用

## 限制提示示例

```json
{
  "id": "sleep",
  "name": "睡眠",
  "i18n_key": "life.tag.sleep",
  "use_restricted_i18n_key": "life.tag.sleep.use_restricted",
  "fire_restricted_i18n_key": "life.tag.sleep.fire_restricted"
}
```

对应的语言文件应该包含：

```json
{
  "life.tag.sleep": "睡眠",
  "life.tag.sleep.use_restricted": "无法在睡眠状态下使用物品",
  "life.tag.sleep.fire_restricted": "睡眠中无法触发此事件"
}
```
