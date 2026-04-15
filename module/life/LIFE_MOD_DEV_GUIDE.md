# LIFE Mod 开发指南（0.3）

本文档用于第三方开发者编写 LIFE 模组，目标是做到“新增文件即可注册”。

当前能力核对（与现有代码一致）：
- 已接入：`status/`、`buff/`、`item/`、`nutrition/`、`lang/`、`event_trigger/`、`event_outcome/`（由内置加载流程自动处理）。
- 可扩展：自定义资源可通过 `register_resource_hook()` 挂入同一事务。
- 事务回滚：失败时会回滚 `status/buff/item/nutrition/lang/event_trigger/event_outcome` 与已注册 hook 资源。

## 1. 目录结构
推荐的 mod 包结构：

```text
mod/{your_mod}/
├─ pack_info.json
├─ lang/
│  └─ *.json
├─ nutrition/
│  └─ *.json
├─ status/
│  └─ *.json
├─ buff/
│  ├─ class.json              ← 可选：分类注册
│  ├─ potion/
│  │  ├─ class.json
│  │  └─ *.json
│  └─ status/
│     ├─ class.json
│     └─ *.json
├─ item/
│  ├─ consumables/
│  │  ├─ class.json
│  │  └─ *.json
│  └─ foods/
│     ├─ class.json
│     └─ *.json
├─ event_trigger/
│  ├─ outdoor/
│  │  ├─ class.json
│  │  └─ *.json
│  └─ learning/
│     ├─ class.json
│     └─ *.json
└─ event_outcome/
   └─ *.json
```

当前 0.3 版本核心对 mod 目录的自动接入范围是 `status` / `buff` / `item` / `nutrition` / `lang` / `event_trigger` / `event_outcome`。
其中 `lang` 目录约定为 `mod/{your_mod}/lang/xx_xx.json`，会在加载时自动接入翻译系统并在回滚时移除。
`register_life_nutrition_hook()` 仍可用，但主要用于旧版本兼容或自定义钩子行为；默认内置加载器已经自动处理 `nutrition/`。

## 2. pack_info.json 约定
最小字段：

```json
{
  "id": "demo.mod",
  "name": "Demo Mod",
  "version": "0.1.0",
  "requires": [],
  "conflicts": []
}
```

字段说明：
- `id`: mod 唯一标识。
- `requires`: 前置 mod 列表。
- `conflicts`: 冲突 mod 列表。

## 3. status json 规则
每个状态定义建议包含：
- `id` 唯一标识（如 `hp`）
- `name` 展示名（兜底文本）
- `i18n_key` 对应语言键（推荐）
- `default` 初始值
- `min` 下限
- `max` 上限
- `order` 排序（数字越小越靠前）

可选区间效果（与 nutrition 同风格）：
- `effects`: 区间效果列表
- 每条可包含：
  - `min` / `max`: 数值区间（左闭右开）
  - `percent_min` / `percent_max`: 百分比区间（左闭右开）
  - `buff_id`: 命中区间时激活的持续 buff（离开区间自动移除）
  - `states` / `attrs`: 命中区间时每 tick 直接改动（旧式兼容）

百分比区间的计算方式：
- `当前状态值 / 该状态基础上限(max) * 100`
- 例如基础上限 1000，当前值 150，则百分比为 15%。

示例：

```json
{
  "id": "satiety",
  "name": "饱食",
  "i18n_key": "life.state.satiety",
  "default": 80,
  "min": 0,
  "max": 120,
  "order": 50,
  "effects": [
    {
      "percent_min": 10,
      "percent_max": 20,
      "buff_id": "exhausted"
    }
  ]
}
```

i18 说明：
- `i18n_key` 命中时使用翻译文本。
- `name` 始终作为兜底文本（key 缺失或未命中时显示）。

## 4. buff json 规则
每个 buff 至少应包含：
- `id` 唯一标识
- `name` 展示名
- `desc` 或 `description` 描述（推荐）

文案 i18 字段（推荐）：
- `name_i18n_key`: buff 名称翻译键
- `desc_i18n_key`: `desc` 翻译键
- `description_i18n_key`: `description` 翻译键

常见字段：
- 直接改动：`{state_id}`（例如 `hp`、`satiety`）
- 持续改动：`{state_id}s`
- 持续时长：`{state_id}st`
- 叠加规则：`{state_id}sr`，值为 `add/noadd/refresh`
- 上下限：`*_max/*_min/*_max2`（支持数值或百分比字符串）

示例：

```json
{
  "id": "coffee_focus",
  "name": "咖啡专注",
  "name_i18n_key": "life.buff.coffee_focus.name",
  "desc": "短时间提升精神并缓慢消耗体力。",
  "desc_i18n_key": "life.buff.coffee_focus.desc",
  "psc": 8,
  "energys": -1,
  "energyst": 12,
  "energysr": "refresh"
}
```

## 5. item json 规则
每个 item 至少应包含：
- `id`
- `name`
- 推荐 `desc`（用于详情弹窗）

文案 i18 字段（推荐）：
- `name_i18n_key`: item 名称翻译键
- `desc_i18n_key`: `desc` 翻译键
- `description_i18n_key`: `description` 翻译键

可选字段：
- `usable`: 是否可使用（默认 true）
- `nutrition`: 营养改动字典，格式为 `{nutrition_id: delta}`
- 其余状态/持续/上下限字段与 buff 一致

示例：

```json
{
  "id": "protein_bar",
  "name": "能量棒",
  "name_i18n_key": "life.item.protein_bar.name",
  "desc": "小幅恢复体力和心情。",
  "desc_i18n_key": "life.item.protein_bar.desc",
  "usable": true,
  "nutrition": {
    "satiety_meter": 8
  },
  "energy": 4,
  "happy": 2
}
```

## 6. nutrition json 规则
每个 nutrition 定义建议包含：
- `id` 唯一标识
- `name` 展示名
- `i18n_key` 名称翻译键（推荐）
- `default` 初始值
- `min` / `max` 取值边界
- `decay` 每 tick 衰减值
- `effects` 区间效果列表

`effects` 的单条规则结构：
- `min` / `max`: 命中区间，采用左闭右开
- `percent_min` / `percent_max`: 百分比区间，采用左闭右开
- `states`: 命中时每 tick 对状态追加的变化
- `attrs`: 命中时每 tick 对属性追加的变化
- `buff_id`: 命中时激活持续 buff，离开区间自动移除

百分比区间计算：
- `当前营养值 / 该营养基础上限(max) * 100`

示例：

```json
{
  "id": "satiety_meter",
  "name": "饱腹",
  "i18n_key": "life.nutrition.satiety_meter",
  "default": 65,
  "min": 0,
  "max": 100,
  "decay": 2,
  "effects": [
    {
      "percent_min": 60,
      "percent_max": 101,
      "buff_id": "well_fed"
    },
    {
      "percent_min": 0,
      "percent_max": 25,
      "buff_id": "starving"
    }
  ]
}
```

## 7. lang json 规则
语言文件沿用主工程的扁平 key 结构，例如：

```json
{
  "life.mod.example": "模组文案",
  "life.state.satiety": "饱食",
  "life.item.protein_bar.name": "能量棒",
  "life.item.protein_bar.desc": "小幅恢复体力和心情。",
  "life.buff.coffee_focus.name": "咖啡专注",
  "life.buff.coffee_focus.desc": "短时间提升精神并缓慢消耗体力。",
  "life.trigger.explore_park.name": "逛公园",
  "life.trigger.explore_park.desc": "带{character_name}去公园散步。",
  "life.outcome.park_find_flower.name": "发现小花",
  "life.outcome.park_find_flower.desc": "在草丛里发现了一朵漂亮的小花。"
}
```

目录要求：
- 文件路径必须位于 mod 根目录下的 `lang/xx_xx.json`。
- 例如：`mod/demo.langpack/lang/zh_cn.json`、`mod/demo.langpack/lang/en_us.json`。

建议：
- 不要覆盖无关 key，尽量只提供本 mod 需要的新增或定制文本。
- 如需覆盖已有 key，确认不同语言文件都同步提供，避免出现中英文不一致。

## 8. event_trigger json 规则（事件触发器）

事件触发器是玩家的交互入口，可在养成面板的"事件"标签页中触发。

每个触发器至少应包含：
- `id` 唯一标识
- `name` 展示名

文案 i18n 字段（推荐）：
- `name_i18n_key`
- `desc_i18n_key` / `description_i18n_key`

特有字段：
- `cooldown_s`: 触发后冷却秒数
- `duration_s`: 执行持续时间（秒）。当 > 0 时，触发后不会立即产出结果，而是进入"执行中"状态，倒计时结束后才执行随机池和必定触发效果，期间按钮显示"执行中"
- `mutex`: 互斥触发器 ID 列表（单向）。若 A 声明与 B 互斥，则 B 处于冷却时 A 不可使用；但 B 未声明与 A 互斥时，B 不受 A 的冷却影响
- `requires_item`: 背包条件（必须拥有）。支持字符串或字符串数组；未满足时触发失败
- `requires_no_item`: 背包条件（必须不拥有）。支持字符串或字符串数组；不满足时触发失败
- `guaranteed`: 必定触发的效果（字典）
  - `items`: 物品列表 `[{"id": "xxx", "count": 1}]`
  - `buffs`: buff ID 列表 `["buff_id"]`
  - `outcomes`: 事件结果 ID 列表 `["outcome_id"]`
- `random_pools`: 随机抽取池列表，每个池独立计算

随机池规则：
- 每个池包含 `entries` 列表
- 每个 entry 有 `type`（`item`/`buff`/`outcome`）、`id`、`chance`（概率百分比）
- item 类型额外支持 `count` 字段
- 若池内所有 chance 之和 ≤ 100%：单次抽取
- 若 > 100% 且 ≤ 300%：所有 chance 除以 2，抽取 2 次
- 若 > 300%：所有 chance 除以 4，抽取 4 次

示例：

```json
{
  "id": "explore_park",
  "name": "逛公园",
  "name_i18n_key": "life.trigger.explore_park.name",
  "desc": "带{character_name}去公园散步。",
  "desc_i18n_key": "life.trigger.explore_park.desc",
  "cooldown_s": 120,
  "duration_s": 30,
  "requires_item": "library_card",
  "requires_no_item": ["injured_badge"],
  "mutex": ["read_book"],
  "guaranteed": {
    "items": [],
    "buffs": [],
    "outcomes": []
  },
  "random_pools": [
    {
      "entries": [
        {"type": "outcome", "id": "park_find_flower", "chance": 40},
        {"type": "outcome", "id": "park_meet_cat", "chance": 30},
        {"type": "outcome", "id": "park_fresh_air", "chance": 50}
      ]
    }
  ]
}
```

## 9. event_outcome json 规则（事件随机结果）

事件结果可以被触发器或其他结果链式触发。

每个结果至少应包含：
- `id` 唯一标识
- `name` 展示名

文案 i18n 字段与触发器一致。

结构字段：
- `guaranteed`: 与触发器相同，必定触发的效果
- `random_pools`: 与触发器相同，随机抽取池
- `effects`: 即时状态变更字典，格式为 `{state_id: delta}`。触发此结果时立即将对应状态加/减指定数值。例如 `{"happy": 8, "energy": -5}` 表示心情 +8、体力 -5

事件结果可以链式引用其他事件结果（通过 `guaranteed.outcomes` 或 `random_pools` 中 `type: "outcome"`），系统会自动递归调用，最大深度为 10。

示例：

```json
{
  "id": "park_find_flower",
  "name": "发现小花",
  "name_i18n_key": "life.outcome.park_find_flower.name",
  "desc": "{character_name}在草丛里发现了一朵漂亮的小花。",
  "desc_i18n_key": "life.outcome.park_find_flower.desc",
  "effects": {"happy": 8, "energy": -5},
  "guaranteed": {
    "items": [{"id": "flower", "count": 1}],
    "buffs": ["happy_mood"],
    "outcomes": []
  },
  "random_pools": [
    {
      "entries": [
        {"type": "item", "id": "rare_seed", "count": 1, "chance": 10},
        {"type": "outcome", "id": "butterfly_appears", "chance": 20}
      ]
    }
  ]
}
```

## 10. class.json 分类注册系统

`item/`、`event_trigger/`、`buff/` 目录支持通过 `class.json` 被动注册分类标签。UI 会在对应标签页中生成子标签栏，按分类筛选展示。

### 基本规则
- 在子目录中放置 `class.json`，系统会向上查找最近的 `class.json` 来确定分类。
- `class.json` 不是数据文件，不会作为 item/buff/trigger 被加载。
- 一个目录下只需一个 `class.json`，其内所有同级和子级的数据文件都继承该分类。
- 没有 `class.json` 的数据文件归入"其他"分类。

### class.json 格式

```json
{
  "classes": ["outdoor"],
  "class_definitions": {
    "outdoor": {
      "name": "户外",
      "name_i18n_key": "life.trigger_class.outdoor"
    }
  }
}
```

字段说明：
- `classes`: 分类 ID 列表。该目录下的所有 JSON 数据文件都会被标记为这些分类。
- `class_definitions`: 分类定义字典（可选）。提供展示名和 i18n key。若省略，系统使用 `life.{type}_class.{cls_id}` 作为默认 i18n key。

### 适用范围
| 目录 | 分类 key 前缀 | 说明 |
|------|---------------|------|
| `item/` | `life.item_class.*` | 物品分类，如食物、消耗品 |
| `event_trigger/` | `life.trigger_class.*` | 事件触发器分类，如户外、学习、社交 |
| `buff/` | `life.buff_class.*` | 效果分类，如药剂、状态、增益 |

### Mod 中的使用
在 mod 的 `item/`、`event_trigger/`、`buff/` 子目录中放置 `class.json` 即可自动注册。建议同时在 `lang/` 中提供对应 i18n key。

示例目录结构：
```text
mod/my_mod/
├─ event_trigger/
│  └─ adventure/
│     ├─ class.json           ← {"classes": ["adventure"], "class_definitions": {...}}
│     └─ adventure_events.json
├─ buff/
│  └─ curse/
│     ├─ class.json
│     └─ curse_buffs.json
└─ lang/
   ├─ zh_cn.json              ← {"life.trigger_class.adventure": "冒险", "life.buff_class.curse": "诅咒"}
   └─ en_us.json
```

## 11. schema 校验说明
0.3 已内置字段校验，会在日志输出：
- `error`: 类型错误、非法规则值、关键字段缺失
- `warn`: 未识别字段（会透传，不阻断）

其中 item 的 `nutrition` 字段会校验：
- 顶层必须是字典
- 每个 value 必须是数值
- 若引用了未注册 nutrition id，会记录 warn，并在运行时忽略

日志格式示例：

```text
[Life][schema][warn] module/life/buff/demo.json record=coffee_focus field=foo msg=未识别字段，将按原始逻辑透传
```

## 12. 最佳实践
- 使用稳定 `id`，避免后续重命名导臨旧存档无法正确映射。
- 所有可展示实体补全 `desc`，便于 UI 一致展示。
- 对可展示实体（status/nutrition/item/buff/event_trigger/event_outcome）统一提供 i18n key，并保留 `name/desc` 兆底文本。
- 持续效果请显式给出 `*st` 与 `*sr`，避免默认行为歧义。
- 对 `*_max2` 谨慎使用，指数增长容易导致数值失控。
- 新增展示文案时同步提供 `lang/zh_cn.json` 与 `lang/en_us.json`，避免只在单语言下可见。
- food/item 中引用的 nutrition id 应与 `nutrition/*.json` 保持一致，避免运行时被忽略。

## 13. 兼容建议
- 每次发版更新 `version`，并维护简单变更日志。
- 如需依赖其他 mod，使用 `requires` 明确声明。
- 与已知重做同类内容的 mod 填入 `conflicts`。

## 14. 后续扩展建议
- 若 mod 需要接入未来新增资源类型，优先遵循统一资源钩子协议，而不是绕过 `LifeModRegistry` 直接改全局状态。
- 资源装配应满足“可加载、可回滚、可诊断”三项要求，避免产生半加载状态。

## 15. 最小可运行示例（区间 buff）

下面给出一个可直接复制的最小示例，演示状态区间 buff 的两种写法：
- 数值区间：`min/max`
- 百分比区间：`percent_min/percent_max`

示例目录：

```text
mod/demo.threshold/
├─ pack_info.json
├─ status/
│  └─ status.json
└─ buff/
   └─ status/
      └─ status_buffs.json
```

`pack_info.json`：

```json
{
  "id": "demo.threshold",
  "name": "Threshold Demo",
  "version": "0.1.0",
  "requires": [],
  "conflicts": []
}
```

`status/status.json`（仅示意 `energy`）：

```json
[
  {
    "id": "energy",
    "name": "ENERGY",
    "i18n_key": "life.state.energy",
    "default": 1000,
    "min": 0,
    "max": 1000,
    "order": 40,
    "effects": [
      {
        "min": 800,
        "max": 1200,
        "buff_id": "strong"
      },
      {
        "percent_min": 10,
        "percent_max": 20,
        "buff_id": "exhausted"
      }
    ]
  }
]
```

`buff/status/status_buffs.json`：

```json
[
  {
    "id": "strong",
    "name": "强壮",
    "desc": "体力充沛，力量显著提升。",
    "str": 4
  },
  {
    "id": "exhausted",
    "name": "疲惫",
    "desc": "力量与敏捷下降，行动明显变得迟缓。",
    "str": -2,
    "agi": -2
  }
]
```

行为说明：
- `strong`: 当 `800 <= energy < 1200` 时激活，离开区间自动移除。
- `exhausted`: 当 `10% <= energy/base_max*100 < 20%` 时激活，离开区间自动移除。

## 16. 接口覆盖清单（0.3）

内置自动事务接入目录：
- `status/`
- `buff/`
- `item/`
- `nutrition/`
- `lang/`
- `event_trigger/`
- `event_outcome/`

可扩展（非目录约定、需要钩子）：
- 其它自定义资源类型：通过 `register_resource_hook()` 接入。

兼容接口（可选）：
- `register_life_nutrition_hook()`：仍可使用，但默认内置流程已自动处理 `nutrition/`。

## 17. 快速验证步骤

1. 放置示例目录后启动程序。
2. 在调试窗口将体力设为 `900`，确认 `strong` 生效（力量 +4）。
3. 将体力设为 `150`（基础上限 1000 的 15%），确认 `exhausted` 生效（力量/敏捷 -2）。
4. 将体力设为 `250`，确认 `exhausted` 自动移除。
5. 查看日志，确认无 schema error。

## 18. 常见错误排查

### 1) 百分比区间写成 0~1 导致不生效
- 错误示例：`percent_min: 0.1, percent_max: 0.2`
- 正确写法：`percent_min: 10, percent_max: 20`
- 原因：百分比区间单位是 `0~100`，不是 `0~1`。

### 2) 区间边界理解错误
- 系统使用左闭右开：`[min, max)`。
- 例如 `min=800, max=1200`：命中 `800 <= value < 1200`，`1200` 不命中。
- 百分比区间同理：`percent_min <= percent < percent_max`。

### 3) 百分比基准用错
- 状态百分比基准：`当前状态值 / 该状态基础上限(max) * 100`
- 营养百分比基准：`当前营养值 / 该营养基础上限(max) * 100`
- 注意：这里是“基础上限”，不是实时修正后的上限。

### 4) buff_id 存在但效果没变化
- 检查对应 buff 文件是否被加载到 `buff/` 目录链路。
- 检查 `id` 拼写是否完全一致（区分大小写）。
- 检查 buff 是否只有描述没有数值字段（如缺少 `str`/`agi`/`hp` 等）。

### 5) 进入区间后生效，离开区间不恢复
- 先确认使用的是 `buff_id` 方式（托管 buff）。
- 若用 `states/attrs` 旧式每 tick 直改，则不会自动回滚，属于设计行为。
- 建议优先使用 `buff_id` 管理可逆效果。

### 6) 多个区间规则互相覆盖
- 同一状态/营养可同时命中多条规则并叠加效果。
- 建议避免重叠区间，或显式规划叠加策略。

### 7) Mod 加载后无任何变化
- 检查目录层级是否正确：`mod/{id}/status/*.json`、`mod/{id}/buff/**/*.json`。
- 检查 `pack_info.json` 是否有效且 `id` 唯一。
- 检查是否被 `requires/conflicts/requires_versions` 拦截。

### 8) 快速自检清单（建议按顺序）
1. `pack_info.json` 是否可解析且字段齐全。
2. `status/nutrition` 区间字段是否使用正确单位与边界。
3. `buff_id` 是否存在于已加载 buff 注册表。
4. 调试窗口中状态值是否确实进入目标区间。
5. 日志中是否出现 schema error/warn 与依赖冲突提示。
