# LIFE Mod 开发指南（0.3）

本文档用于第三方开发者编写 LIFE 模组，目标是做到"新增文件即可注册"。

当前能力核对（与现有代码一致）：

- 已接入：`status/`、`buff/`、`item/`、`nutrition/`、`lang/`、`event_trigger/`、`event_outcome/`、`passive_buff/`、`attrs/`、`level/`（由内置加载流程自动处理）。
- 可扩展：自定义资源可通过 `register_resource_hook()` 挂入同一事务。
- 事务回滚：失败时会回滚所有上述目录资源与已注册 hook 资源。

> **协议版本说明**：`pack_info.json` 中可声明 `"min_protocol": "0.3"` 以要求宿主至少支持 0.3 协议。0.3 新增了全局等级系统、物品永久属性修正、等级限制、`global_event` tag 字段等功能；低于 0.3 的宿主将忽略这些字段。

---

## 目录

| 章节 | 内容 |
|------|------|
| [1. 目录结构](#1-目录结构) | mod 包推荐目录布局 |
| [2. pack_info.json 约定](#2-pack_infojson-约定) | 元数据字段说明 |
| [3. status json 规则](#3-status-json-规则) | 状态定义与区间效果 |
| [4. buff json 规则](#4-buff-json-规则) | 效果定义与持续改动 |
| [5. item json 规则](#5-item-json-规则) | 物品定义与使用效果 |
| [6. nutrition json 规则](#6-nutrition-json-规则) | 营养定义与区间效果 |
| [7. lang json 规则](#7-lang-json-规则) | 语言文件翻译规范 |
| [8. event_trigger json 规则](#8-event_trigger-json-规则事件触发器) | 事件触发器定义 |
| [9. event_outcome json 规则](#9-event_outcome-json-规则事件结果) | 事件结果与链式触发 |
| [10. passive_buff json 规则](#10-passive_buff-json-规则挂机随机-buff-触发器) | 挂机随机 buff |
| [11. attrs json 规则](#11-attrs-json-规则属性定义) | 属性定义与等级加成 |
| [12. level 全局等级配置](#12-level-全局等级配置03-新增) | 全局角色等级系统 |
| [13. tags json 规则](#13-tags-json-规则与全局封锁03-新增) | 标签注册与全局封锁 |
| [14. class.json 分类注册系统](#14-classjson-分类注册系统) | UI 分类标签页 |
| [15. 标签限制系统](#15-标签限制系统tag-restriction) | buff → 物品/事件限制 |
| [16. 物品/事件等级字段](#16-物品事件等级字段03-新增) | 经验值与等级门槛 |
| [17. schema 校验说明](#17-schema-校验说明) | 内置字段校验 |
| [18. 接口覆盖清单](#18-接口覆盖清单03) | 内置与可扩展接口 |
| [19. 最佳实践](#19-最佳实践) | 开发建议 |
| [20. 兼容建议](#20-兼容建议) | 版本与依赖管理 |
| [21. 最小可运行示例](#21-最小可运行示例区间-buff) | 可复制的完整示例 |
| [22. icon_base64 图标系统](#22-icon_base64-图标系统) | 图标字段说明 |
| [23. 快速验证步骤](#23-快速验证步骤) | 验证流程 |
| [24. 常见错误排查](#24-常见错误排查) | FAQ 与自检清单 |
| [25. 后续扩展建议](#25-后续扩展建议) | 扩展方向 |

---

## 1. 目录结构

推荐的 mod 包结构：

```text
mod/{your_mod}/
├─ pack_info.json              ← 必须：mod 元数据
├─ lang/
│  └─ *.json                   ← 翻译文件（xx_xx.json）
├─ status/
│  └─ *.json                   ← 状态定义
├─ nutrition/
│  └─ *.json                   ← 营养定义
├─ attrs/
│  └─ *.json                   ← 属性定义（支持 char_level_bonuses，0.3）
├─ level/
│  └─ level_setting.json       ← 全局等级配置（0.3）
├─ buff/
│  ├─ class.json               ← 可选：分类注册
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
├─ event_outcome/
│  └─ *.json                   ← 事件结果
├─ tags/
│  └─ *.json                   ← 标签定义（可选，0.3）
└─ passive_buff/
   └─ *.json                   ← 挂机随机 buff 触发器
```

当前 0.3 版本核心对 mod 目录的自动接入范围是 `status` / `buff` / `item` / `nutrition` / `lang` / `event_trigger` / `event_outcome` / `passive_buff` / `attrs` / `level` / `tags`（含 `level_setting.json`）。
其中 `lang` 目录约定为 `mod/{your_mod}/lang/xx_xx.json`，会在加载时自动接入翻译系统并在回滚时移除。

> **注意**：Mod 可以在自己的包中放置 `tags/` 目录来注册新标签（参见[第 13 节](#13-tags-json-规则与全局封锁03-新增)）。标签定义会被合并到全局标签注册表中。

---

## 2. pack_info.json 约定

### 最小字段

```json
{
  "id": "demo.mod",
  "name": "Demo Mod",
  "version": "0.1.0"
}
```

### 完整字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | mod 唯一标识，建议使用 `author.mod_name` 格式 |
| `name` | string | 推荐 | mod 展示名 |
| `version` | string | 推荐 | 语义化版本号（如 `"1.0.0"`） |
| `description` | string | 可选 | mod 简介 |
| `author` | string | 可选 | 作者 |
| `min_protocol` | string | 可选 | 要求宿主最低协议版本（如 `"0.3"`）；不满足时跳过加载 |
| `max_protocol` | string | 可选 | 要求宿主最高协议版本；不满足时跳过加载 |
| `requires` | list | 可选 | 前置 mod ID 列表；缺失时加载失败 |
| `conflicts` | list | 可选 | 冲突 mod ID 列表；同时存在时加载失败 |
| `requires_versions` | dict | 可选 | 依赖版本约束（见下文） |
| `remove_ids` | dict | 可选 | 从注册表中移除指定 ID（见下文） |

### requires_versions

用于指定依赖 mod 的版本约束，格式为 `{mod_id: constraint}`：

```json
{
  "requires_versions": {
    "base.mod": ">=1.0.0",
    "helper.mod": ">=0.5.0"
  }
}
```

约束支持 `>=`、`<=`、`==` 等前缀，使用语义化版本比较。

### remove_ids

用于从宿主注册表中移除指定条目，格式为 `{registry_type: [id_list]}`：

```json
{
  "remove_ids": {
    "buff": ["default_regen"],
    "item": ["old_potion"],
    "status": ["deprecated_stat"]
  }
}
```

支持的 `registry_type` 包括：`buff`、`item`、`event_trigger`、`event_outcome`、`passive_buff`、`status`、`nutrition`、`attrs`。

> **加载顺序与重试机制**：mod 按 `requires` 依赖关系做拓扑排序；无依赖关系的 mod 按 id 字母序排列。
> 
> 加载时采用**延迟重试**策略：
> 1. 按照排序顺序依次尝试加载每个 mod。
> 2. 如果某个 mod 的 `requires` 中声明的前置 mod 尚未加载完成，该 mod 被移入**待加载队列**。
> 3. 继续加载后续 mod，每成功加载一个 mod 后尝试重新加载待加载队列中的所有 mod。
> 4. 所有 mod 遍历完毕后，反复重试待加载队列，直到没有新 mod 能被加载为止。
> 5. 仍留在待加载队列中的 mod 被视为"前置 mod 不存在"，放弃加载并记录 warn 日志。
> 
> 这意味着：即使某个 mod 在排序中排在它的前置 mod 之前（例如因字母序），它也不会加载失败，而是被推迟等待。只有当前置 mod 确实不存在（从未被扫描到）时才会被放弃。
> 
> 事务性回滚已移除——每个 mod 独立加载，失败不影响已加载的 mod。
> 
> **加载日志说明**：
> - **延迟加载日志**：`[Mod]延迟加载: {id} (前置 ['dep_id'] 未就绪)` — 表示 mod 因前置未满足被移入待加载队列。
> - **重试日志**：`[Mod]重试待加载队列 (N 个)...` → `[Mod]重试成功: {id}` — 表示待加载队列中的 mod 被重新尝试并成功加载。
> - **放弃日志**：`[Mod]放弃 {id}: 前置mod未满足: dep_id` — 表示 mod 因前置 mod 不存在而最终放弃。
> - **新增/修改/删除日志**：`[Mod]加载成功: {id} (v1.0) | 新增 buff:['a','b'] item:['c'] | 修改 buff:['d'] | 删除 food:['e']` — 显示每个 mod 加载后对注册表的具体变更。
> 
> `新增` 表示该 mod 提供了新的 ID；`修改` 表示覆盖了已有的 ID；`删除` 表示通过 `remove_ids` 移除了 ID。

---

## 3. status json 规则

每个状态定义建议包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识（如 `hp`） |
| `name` | string | 展示名（兜底文本） |
| `i18n_key` | string | 对应语言键（推荐） |
| `default` | number | 初始值 |
| `min` | number | 下限 |
| `max` | number | 上限 |
| `order` | number | 排序（数字越小越靠前） |
| `effects` | list | 区间效果列表（可选） |

### 区间效果（effects）

每条 effect 可包含：

- `min` / `max`：数值区间（左闭右开）
- `percent_min` / `percent_max`：百分比区间（左闭右开）
- `buff_id`：命中区间时激活的持续 buff（离开区间自动移除）
- `states` / `attrs`：命中区间时每 tick 直接改动（旧式兼容）

百分比区间的计算方式：`当前状态值 / 该状态基础上限(max) × 100`
例如基础上限 1000，当前值 150，则百分比为 15%。

### 示例

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

### i18n 说明

- `i18n_key` 命中时使用翻译文本。
- `name` 始终作为兜底文本（key 缺失或未命中时显示）。

---

## 4. buff json 规则

每个 buff 至少应包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `name` | string | 展示名 |
| `desc` / `description` | string | 描述（推荐） |

### i18n 字段（推荐）

| 字段 | 说明 |
|------|------|
| `name_i18n_key` | buff 名称翻译键 |
| `desc_i18n_key` | `desc` 翻译键 |
| `description_i18n_key` | `description` 翻译键 |

### 显示字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `icon_base64` | string | — | Base64 编码的 PNG 图标，在详情弹窗顶栏展示（参见[第 25 节](#25-icon_base64-图标系统)） |
| `display_in_status_bar` | bool | `false` | 是否在桌宠窗口的 buff 图标栏中显示此 buff 的图标。仅当 `icon_base64` 也提供时有效。 |

### 数值字段

| 格式 | 说明 | 示例 |
|------|------|------|
| `{state_id}` | 使用时直接改动 | `hp: 10` |
| `{state_id}s` | 每 tick 持续改动 | `energys: -1` |
| `{state_id}st` | 持续时长（tick 数） | `energyst: 12` |
| `{state_id}sr` | 叠加规则 | `energysr: "refresh"` |
| `*_max` / `*_min` | 上下限修正（支持数值或百分比字符串如 `"-40%"`） | `hp_max: 50`, `energy_max: "-30%"` |
| `*_max2` | 指数增长上限（谨慎使用） | — |
| `nutrition` | dict | 使用时一次性营养改动，格式 `{nutrition_id: delta}` |
| `exp` | number | 应用此 buff 时给予的经验值 |
| `attr_exp` | dict | 属性经验，格式 `{attr_id: delta}` |
| `permanent_attr_delta` | dict | 永久属性修正（不随 buff 移除回滚），格式 `{attr_id: delta}` |

叠加规则值：`add`（叠加）/ `noadd`（不叠加）/ `refresh`（刷新时长）

### 条件与自动触发字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `chance` | number | 概率系统：正值 = 每 tick 以该百分比概率应用 buff；负值 = 每 tick 以该绝对值百分比概率移除同名 buff |
| `consume_self` | bool | `true` 时 buff 执行一次性效果但不注册为持久效果（即 trigger 式用法） |
| `requires_buff` | string / list | 必须拥有至少一个指定 buff 才允许自动应用（配合 `chance` 使用） |
| `requires_no_buff` | string / list | 必须不拥有任何指定 buff 才允许自动应用 |
| `min_level` | int | 应用 buff 的最低等级要求 |
| `attribute` | string | 属性 ID，配合 `status` 列表实现属性区间效果（参见下方说明） |
| `status` | list | 属性区间规则列表，格式 `[{"min": 0, "max": 5, "effects": {...}}]` |
| `fail_messages` | dict | 自定义失败提示，key 为拒绝原因 code，value 为 i18n key 或文本 |

### 属性区间效果（attribute + status）

`attribute` 和 `status` 配合可实现"根据属性值所在区间自动激活效果"：

```json
{
  "id": "titan_strength",
  "name": "泰坦之力",
  "attribute": "str",
  "status": [
    {"min": 0, "max": 5, "effects": {"str": -2}},
    {"min": 15, "max": 999, "effects": {"str": 5}}
  ]
}
```

当角色的 `str` 属性值在 `[0, 5)` 区间时自动应用 str −2；在 `[15, 999)` 区间时自动应用 str +5。`effects` 字典中的 key 可以是状态（state）或属性（attr），value 为每 tick 的改动量。

### 连锁与清理字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `buff_refs` | list | buff ID 列表，应用此 buff 时同时应用引用的 buff |
| `clear_buffs` | string / list | 应用此 buff 时移除指定 buff |

### 标签限制字段

| 字段 | 说明 |
|------|------|
| `restrict_item_tags` | 激活期间仅允许带有这些标签的物品被使用（参见[第 15 节](#15-标签限制系统tag-restriction)） |
| `restrict_trigger_tags` | 激活期间仅允许带有这些标签的事件被触发 |

### 示例

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

---

## 5. item json 规则

每个 item 至少应包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `name` | string | 展示名 |
| `desc` | string | 描述（推荐，用于详情弹窗） |

### i18n 字段（推荐）

| 字段 | 说明 |
|------|------|
| `name_i18n_key` | item 名称翻译键 |
| `desc_i18n_key` | `desc` 翻译键 |
| `description_i18n_key` | `description` 翻译键 |

### 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `usable` | bool | `true` | 是否可使用 |
| `unique` | bool | `false` | 是否唯一持有；为 true 时玩家最多持有 1 个 |
| `tags` | list | `[]` | 标签列表，用于标签限制系统匹配（参见[第 15 节](#15-标签限制系统tag-restriction)） |
| `icon_base64` | string | — | Base64 编码的 PNG 图标，在详情弹窗顶栏展示（参见[第 25 节](#25-icon_base64-图标系统)） |
| `nutrition` | dict | — | 营养改动字典，格式为 `{nutrition_id: delta}` |
| `buff_refs` | list | `[]` | buff ID 列表，使用该物品时自动触发对应 buff |
| `exp` | number | `0` | 使用物品时给予的经验值（0.3，可为负数） |
| `attr_exp` | dict | — | 属性经验，格式 `{attr_id: delta}` |
| `min_level` | int | `0` | 使用物品的最低等级要求（0.3） |
| `cooldown_s` | number | `0` | 使用后的冷却秒数，冷却期间不可再次使用 |
| `passive_exp_bonus` | number | `0` | 持有此物品时每 tick 被动经验加成（0.3） |
| `passive_attr_bonus` | dict | — | 持有此物品时每 tick 被动属性加成，格式 `{attr_id: delta}` |
| `permanent_attr_delta` | dict | — | 使用物品时永久修改属性（0.3），格式为 `{"attr_id": delta}` |
| `clear_buffs` | string / list | — | 使用时移除指定 buff（如 `"ill"` 或 `["ill", "depressed"]`） |
| `fail_messages` | dict | — | 自定义失败提示，key 为拒绝原因 code，value 为 i18n key 或文本 |

其余状态/持续/上下限字段与 buff 一致。

### 示例

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

---

## 6. nutrition json 规则

每个 nutrition 定义建议包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `name` | string | 展示名 |
| `i18n_key` | string | 名称翻译键（推荐） |
| `default` | number | 初始值 |
| `min` | number | 取值下限 |
| `max` | number | 取值上限 |
| `decay` | number | 每 tick 衰减值 |
| `effects` | list | 区间效果列表 |

### effects 单条规则结构

| 字段 | 说明 |
|------|------|
| `min` / `max` | 命中区间（左闭右开） |
| `percent_min` / `percent_max` | 百分比区间（左闭右开） |
| `states` | 命中时每 tick 对状态追加的变化 |
| `attrs` | 命中时每 tick 对属性追加的变化 |
| `buff_id` | 命中时激活持续 buff，离开区间自动移除 |

百分比区间计算：`当前营养值 / 该营养基础上限(max) × 100`

### 示例

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

---

## 7. lang json 规则

语言文件沿用主工程的扁平 key 结构。

### 目录要求

- 文件路径必须位于 mod 根目录下的 `lang/xx_xx.json`。
- 例如：`mod/demo.langpack/lang/zh_cn.json`、`mod/demo.langpack/lang/en_us.json`。

### 示例

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

### 建议

- 不要覆盖无关 key，尽量只提供本 mod 需要的新增或定制文本。
- 如需覆盖已有 key，确认不同语言文件都同步提供，避免出现多语言不一致。
- 纯语言包 mod（仅包含 `lang/`）可正常工作，无需其他资源目录。

---

## 8. event_trigger json 规则（事件触发器）

事件触发器是玩家的交互入口，可在养成面板的"事件"标签页中触发。

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `name` | string | 展示名 |

### i18n 字段（推荐）

- `name_i18n_key`
- `desc_i18n_key` / `description_i18n_key`

### 特有字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `icon_base64` | string | Base64 编码的 PNG 图标，在详情弹窗顶栏展示（参见[第 25 节](#25-icon_base64-图标系统)） |
| `cooldown_s` | number | 触发后冷却秒数 |
| `duration_s` | number | 执行持续时间（秒）。> 0 时进入"执行中"状态，倒计时结束后才执行 |
| `mutex` | list | 互斥触发器 ID 列表（单向）。若 A 声明与 B 互斥，则 B 冷却时 A 不可使用 |
| `tags` | list | 标签列表，用于标签限制系统（参见[第 15 节](#15-标签限制系统tag-restriction)） |
| `requires_item` | string / list | 背包条件（必须拥有），未满足时触发失败 |
| `requires_no_item` | string / list | 背包条件（必须不拥有），不满足时触发失败 |
| `costs` | dict | 触发前状态消耗，格式如 `{"energy": 100, "psc": 50}` |
| `tags_mode` | string | 标签模式：`normal` / `global` / `reverse_global` |
| `mutex_by_tag` | bool | `true` 时与执行中且共享任一 tag 的事件互斥 |
| `exp` | number | 触发器给予的经验值（0.3） |
| `min_level` | int | 触发的最低等级要求（0.3） |
| `fail_messages` | dict | 自定义失败提示，key 为拒绝原因 code，value 为 i18n key 或文本 |
| `guaranteed` | dict | 必定触发的效果 |
| `random_pools` | list | 随机抽取池列表 |

### guaranteed 结构

```json
{
  "items": [{"id": "xxx", "count": 1}],
  "buffs": ["buff_id"],
  "outcomes": ["outcome_id"]
}
```

### random_pools 规则

- 每个池包含 `entries` 列表，各池独立计算。
- 每个 entry 字段：

| 字段 | 说明 |
|------|------|
| `type` | `"item"` / `"buff"` / `"outcome"` |
| `id` | 对应实体 ID |
| `chance` | 基础概率（百分比，0~100） |
| `flat_bonus` | 常量概率修正（可为负），在 chance 基础上直接叠加 |
| `count` | 仅 item 类型：获取数量 |
| `attr_bonus` | 属性加成字典 `{"attr_id": multiplier}`；有效概率 = max(0, base_chance + Σ(attr_val × mult)) |
| `state_bonus` | 状态加成字典 `{"state_id": multiplier}`；有效概率额外叠加 Σ(state_val × mult) |

每个 pool 还支持可选 `fallback`：当 roll 落入 no-fire 区间时触发该条目。结构与 entry 一致（`type/id/count`）。

**归一化算法**：
1. `base_no_fire = max(0, 100 − Σbase_chances)`（不受属性影响）
2. 若 `Σeffective_chances + base_no_fire > 100`：整体等比缩放到 100%
3. 单次 roll，落在 no-fire 区则不触发任何条目

### 示例

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

---

## 9. event_outcome json 规则（事件结果）

事件结果可以被触发器或其他结果链式触发。

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `name` | string | 展示名 |

### i18n 字段

与 event_trigger 一致：`name_i18n_key`、`desc_i18n_key` / `description_i18n_key`。

### 结构字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `icon_base64` | string | Base64 编码的 PNG 图标，在详情弹窗顶栏展示（参见[第 25 节](#25-icon_base64-图标系统)） |
| `guaranteed` | dict | 与触发器相同，必定触发的效果 |
| `random_pools` | list | 与触发器相同，随机抽取池 |
| `effects` | dict | 即时状态变更，格式为 `{state_id: delta}` |
| `permanent_attr_delta` | dict | 触发结果时永久修改属性，格式为 `{attr_id: delta}` |
| `clear_buffs` | string / list | 触发结果时移除指定 buff |
| `exp` | number | 触发结果时给予的经验值（0.3） |
| `min_level` | int | 最低等级要求，用于分支结果过滤（0.3） |

事件结果可以链式引用其他事件结果（通过 `guaranteed.outcomes` 或 `random_pools` 中 `type: "outcome"`），系统会自动递归调用，**最大深度为 10**。

### 示例

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

---

## 10. passive_buff json 规则（挂机随机 buff 触发器）

`passive_buff/` 目录内的 JSON 定义"挂机触发器"，每 tick 按概率自动尝试触发。

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `base_chance` | number | 触发概率（百分比，0~100） |

### 可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 展示名（仅用于日志识别） |
| `requires_buff` | string / list | 必须拥有指定 buff 才允许触发 |
| `requires_no_buff` | string / list | 必须不拥有指定 buff 才允许触发 |
| `attr_conditions` | list | 属性区间条件，格式 `[{"attr": "vit", "min": 0, "max": 5}]` |
| `attr_bonus` | dict | 属性加成字典 `{"attr_id": multiplier}`；有效概率 = max(0, base_chance + Σ(attr_val × mult)) |
| `on_trigger` | dict | 触发后执行的操作 |

### on_trigger 结构

| 字段 | 说明 |
|------|------|
| `buff_id` | 应用指定 buff |
| `duration_formula` | buff 持续 tick 公式（仅 `buff_id` 生效时），支持 `base`、`terms`、`min`、`max` |
| 其他 | 直接状态/营养变化，字段与 buff 一致（如 `hp: -5`） |

`duration_formula` 示例：

```json
{
  "buff_id": "ill",
  "duration_formula": {
    "base": 1200,
    "terms": [{"attr": "vit", "coeff": -60}],
    "min": 60,
    "max": 1200
  }
}
```

### 示例

```json
[
  {
    "id": "cold_chance",
    "name": "随机感冒",
    "base_chance": 5.0,
    "requires_no_buff": ["sick", "protected"],
    "attr_conditions": [{"attr": "vit", "max": 8}],
    "attr_bonus": {"vit": -0.5},
    "on_trigger": {"buff_id": "sick"}
  }
]
```

说明：体质 ≤ 8 且未生病/受保护时，每 tick 有 `max(0, 5 + vit × (−0.5))%` 概率触发感冒 buff。

---

## 11. attrs json 规则（属性定义）

`attrs/` 目录内的 JSON 定义属性项。不存在则回退到内置 7 个属性（vit/str/spd/agi/spi/int/ill）。

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |

### 推荐字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | string | — | 展示名 |
| `i18n_key` | string | `life.attr.{id}` | 名称翻译键 |
| `color` | string | — | 主题色（十六进制，如 `#e06c75`） |
| `initial` | number | `10.0` | 初始属性值 |
| `order` | number | — | 排序（数字越小越靠前） |

### level_table（属性自身经验系统，可选）

```json
"level_table": [
  {"level": 1, "exp_required": 100, "permanent_bonus": {"hp_max": 10}},
  {"level": 2, "exp_required": 250, "permanent_bonus": {"hp_max": 20}}
]
```

### char_level_bonuses（0.3 新增）

全局角色等级驱动的属性加成。支持两种类型，可同时声明多条并互相叠加。

**类型一：到达指定等级时一次性加成（at_level）**

```json
{"type": "at_level", "level": 10, "bonus": {"str": 2}}
```

| 字段 | 说明 |
|------|------|
| `level` | 触发等级（整数，≥ 1） |
| `bonus` | 属性加成字典 `{"attr_id": delta}` |

**类型二：每 X 级固定加成（per_levels）**

```json
{"type": "per_levels", "every": 5, "bonus": {"str": 1}, "min_level_offset": 0}
```

| 字段 | 说明 |
|------|------|
| `every` | 每隔几级触发一次（整数，≥ 1） |
| `bonus` | 属性加成字典 |
| `min_level_offset` | 最低计算等级偏移值（默认 0）。首次触发等级 = `min_level_offset + every + 1` |

> 例：`every=5, min_level_offset=20` → 首次触发需达到第 26 级

### 完整示例

```json
[
  {
    "id": "vit",
    "name": "体质",
    "i18n_key": "life.attr.vit",
    "color": "#e06c75",
    "initial": 10,
    "order": 10,
    "level_table": [
      {"level": 1, "exp_required": 100, "permanent_bonus": {"hp_max": 5}},
      {"level": 2, "exp_required": 250, "permanent_bonus": {"hp_max": 10}}
    ],
    "char_level_bonuses": [
      {"type": "at_level", "level": 10, "bonus": {"vit": 1}}
    ]
  },
  {
    "id": "str",
    "name": "力量",
    "i18n_key": "life.attr.str",
    "color": "#d4834a",
    "initial": 10,
    "order": 20,
    "char_level_bonuses": [
      {"type": "at_level",   "level": 10, "bonus": {"str": 2}},
      {"type": "per_levels", "every": 5,  "bonus": {"str": 1}, "min_level_offset": 0}
    ]
  },
  {
    "id": "int",
    "name": "智力",
    "i18n_key": "life.attr.int",
    "color": "#8b6fd6",
    "initial": 10,
    "order": 60
  }
]
```

说明（以 `str` 为例）：到达第 10 级时一次性 str +2；从第 6 级起每 5 级（第 6、11、16…级）str +1。两种类型同时生效，加成累加。

---

## 12. level 全局等级配置（0.3 新增）

0.3 新增了一套独立于属性经验/等级系统的**全局角色等级系统**，由 `level/level_setting.json` 驱动。
mod 可在包内放置 `level/level_setting.json` 来**整体替换**内置配置（不做合并）。

### 替换规则

- 将 `level_setting.json` 放在 mod 包根目录下的 `level/` 子目录中。
- 加载时整体替换内置配置，回滚时恢复原始配置。
- 若替换后 `max_level < profile.level`，系统自动将当前等级 clamp 到新 `max_level`，经验值不做额外处理。

### level_setting.json 格式

```json
{
  "initial_exp_required": 100,
  "passive_exp_per_tick": 1.0,
  "growth_ranges": [
    {"from_level": 1, "to_level": 10, "exp_growth": 10},
    {"from_level": 11, "to_level": 20, "exp_growth": 15}
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `initial_exp_required` | float | 1 级升 2 级所需经验值（必须 > 0） |
| `passive_exp_per_tick` | float | 每 tick 基础被动经验（不含物品/buff 加成，必须 ≥ 0） |
| `growth_ranges` | list | 各等级段的升级经验增长量配置 |

### growth_ranges 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `from_level` | int | 区间起始等级（含，≥ 1） |
| `to_level` | int | 区间终止等级（含，≥ from_level） |
| `exp_growth` | float | 该区间内每升一级相比上一级的经验增量（支持负数，但不得导致任意等级升级经验 ≤ 0） |

### 最高等级推导规则

将 `growth_ranges` 按 `from_level` 升序排列后，找到第一个断层（相邻区间 `to_level + 1 ≠ 下一个 from_level`），截断于此。只写了一段完整区间时，其 `to_level` 即为最高等级。

### 经验表预计算

`exp_table[level]` = 从 level 升到 level+1 所需经验值，由 `initial_exp_required` 与各区间 `exp_growth` 累加预计算得出。最高等级无对应表项（已到顶）。

### 示例

20 级上限，前 10 级每级需额外 +10 经验，后 10 级额外 +15：

```json
{
  "initial_exp_required": 100,
  "passive_exp_per_tick": 0.5,
  "growth_ranges": [
    {"from_level": 1, "to_level": 10, "exp_growth": 10},
    {"from_level": 11, "to_level": 20, "exp_growth": 15}
  ]
}
```

---

## 13. tags json 规则与全局封锁（0.3 新增）

### tags.json 格式

```json
{
  "id": "first_aid",
  "buff_id": "dying",
  "global_event": true
}
```

### global_event 字段

| 字段值 | buff 激活时 | 不带此 tag 的物品/事件 |
|--------|-------------|----------------------|
| `true` | 触发全局封锁 | 被拒绝（reason = `tag_restricted:{id}`） |
| `false` / 缺失 | 无封锁效果 | 正常可用 |

- `global_event: true`：当 `buff_id` 对应的 buff 激活时，封锁所有**不含该 tag** 的物品/事件。
- `global_event: false` 或字段缺失：tag 仅用于展示/分类，不触发全局封锁逻辑。

### Mod 注册新标签

Mod 可以在包根目录下创建 `tags/` 目录，放置 JSON 文件来注册新标签。标签定义会被合并到全局标签注册表中。

```text
mod/my_mod/
└─ tags/
   └─ tags.json    ← 标签定义
```

```json
{
  "id": "poison",
  "buff_id": "poisoned",
  "i18n_key": "life.tag.poison",
  "global_event": true
}
```

支持的字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 标签唯一标识 |
| `buff_id` | string | 关联的 buff ID（该 buff 激活时触发封锁） |
| `i18n_key` | string | 标签名称翻译键 |
| `color` | string | 颜色（十六进制，如 `#e06c75`），保留字段 |
| `global_event` | bool | `true` 时触发全局封锁 |
| `use_restricted_i18n_key` | string | 物品被封锁时的自定义提示翻译键 |
| `fire_restricted_i18n_key` | string | 事件被封锁时的自定义提示翻译键 |

> Mod 注册的标签会与基础标签合并。同名标签以 mod 的覆盖为准。

---

## 14. class.json 分类注册系统

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

| 字段 | 说明 |
|------|------|
| `classes` | 分类 ID 列表，该目录下所有 JSON 数据文件都被标记为这些分类 |
| `class_definitions` | 分类定义字典（可选），提供展示名和 i18n key。若省略，系统使用 `life.{type}_class.{cls_id}` 作为默认 i18n key |

### 适用范围

| 目录 | 分类 key 前缀 | 说明 |
|------|---------------|------|
| `item/` | `life.item_class.*` | 物品分类，如食物、消耗品 |
| `event_trigger/` | `life.trigger_class.*` | 事件触发器分类，如户外、学习、社交 |
| `buff/` | `life.buff_class.*` | 效果分类，如药剂、状态、增益 |

### Mod 中的使用

在 mod 的 `item/`、`event_trigger/`、`buff/` 子目录中放置 `class.json` 即可自动注册。建议同时在 `lang/` 中提供对应 i18n key。

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

---

## 15. 标签限制系统（Tag Restriction）

当特定 buff 激活时，可以限制玩家只能使用带有指定标签的物品或触发带有指定标签的事件。这是实现"濒死状态仅能使用急救物品/事件"等机制的核心系统。

### 原理

1. buff 记录中声明 `restrict_item_tags` / `restrict_trigger_tags`（字符串数组）。
2. 当该 buff 处于激活状态时，玩家使用物品或触发事件前系统会检查：
   - 物品/事件的 `tags` 与 buff 的 `restrict_*_tags` **有交集** → 允许操作。
   - **无交集** → 操作被拒绝，UI 显示"不可用"按钮并以 toast 提示原因。

### buff 端声明

```json
{
  "id": "dying",
  "name": "濒死",
  "desc": "生命体征微弱，仅能进行急救相关的操作。",
  "restrict_item_tags": ["first_aid"],
  "restrict_trigger_tags": ["first_aid"]
}
```

### 物品端声明

```json
{
  "id": "glucose_iv",
  "name": "葡萄糖补液",
  "usable": true,
  "tags": ["first_aid"],
  "buff_refs": ["glucose_iv_drip"]
}
```

### 事件端声明

```json
{
  "id": "hospitalization",
  "name": "住院",
  "tags": ["first_aid"],
  "duration_s": 60,
  "guaranteed": {
    "buffs": ["hospitalized"]
  }
}
```

### 内置示例：濒死急救

| 组件 | 文件位置 | 说明 |
|------|----------|------|
| `dying` buff | `buff/status/dying.json` | HP 0-100 区间自动激活，声明 `restrict_*_tags: ["first_aid"]` |
| `glucose_iv` item | `item/first_aid/first_aid_items.json` | 急救物品，`tags: ["first_aid"]`，给予 1000 tick 的补液 buff |
| `hospitalization` trigger | `event_trigger/first_aid/first_aid_triggers.json` | 急救事件，`tags: ["first_aid"]`，60s 后给予 3600 tick 住院 buff |

### Mod 中使用标签限制

1. 在 mod 的 buff 中添加 `restrict_item_tags` / `restrict_trigger_tags`。
2. 在对应的 item / event_trigger 中添加匹配的 `tags`。
3. 确保 `tags` 中至少有一个值与 buff 的 restrict 列表匹配。
4. 同一物品/事件可以有多个 tag，只需匹配其中一个即可通过限制。

---

## 16. 物品/事件等级字段（0.3 新增）

### item 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `exp` | number | 使用物品时给予的经验值（可为负数） |
| `min_level` | int ≥ 0 | 使用物品的最低等级要求；未达到时返回 `"level_too_low"` |
| `passive_exp_bonus` | number | 持有此物品时每 tick 被动经验加成（持有数量直接倍增） |
| `permanent_attr_delta` | dict | 使用物品时永久修改属性，格式为 `{"attr_id": delta}` |
| `attr_exp` | dict | 预留字段，供 mod 扩展属性经验使用 |

```json
{
  "id": "ancient_tome",
  "name": "古籍",
  "usable": true,
  "min_level": 5,
  "exp": 50,
  "passive_exp_bonus": 2,
  "permanent_attr_delta": {"int": 1}
}
```

### event_trigger 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `exp` | number | 触发器本身给予的经验值（在 `guaranteed` 处理阶段生效） |
| `min_level` | int ≥ 0 | 触发此事件的最低等级要求 |

### event_outcome 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `exp` | number | 触发该结果时给予的经验值 |
| `min_level` | int ≥ 0 | 该结果的最低等级要求（用于分支结果过滤） |

---

## 17. schema 校验说明

0.3 已内置字段校验，会在日志输出：

- `error`：类型错误、非法规则值、关键字段缺失
- `warn`：未识别字段（会透传，不阻断）

其中 item 的 `nutrition` 字段会校验：

- 顶层必须是字典
- 每个 value 必须是数值
- 若引用了未注册 nutrition id，会记录 warn，并在运行时忽略

日志格式示例：

```text
[Life][schema][warn] module/life/buff/demo.json record=coffee_focus field=foo msg=未识别字段，将按原始逻辑透传
```

---

## 18. 接口覆盖清单（0.3）

### 内置自动事务接入目录

| 目录 | 说明 |
|------|------|
| `status/` | 状态定义 |
| `buff/` | 效果定义 |
| `item/` | 物品定义 |
| `nutrition/` | 营养定义 |
| `lang/` | 翻译文件 |
| `event_trigger/` | 事件触发器 |
| `event_outcome/` | 事件结果 |
| `passive_buff/` | 挂机随机 buff 触发器 |
| `attrs/` | 属性定义 |
| `level/` | 全局等级配置（`level_setting.json`，0.3） |
| `tags/` | 标签定义 |

### 可扩展（非目录约定、需要钩子）

- 其它自定义资源类型：通过 `register_resource_hook()` 接入。

### 兼容接口（可选）

- `register_life_nutrition_hook()`：仍可使用，但默认内置流程已自动处理 `nutrition/`。

### 不支持 mod 覆盖的目录

（暂无）

---

## 19. 最佳实践

- 使用稳定 `id`，避免后续重命名导致旧存档无法正确映射。
- 所有可展示实体补全 `desc`，便于 UI 一致展示。
- 对可展示实体（status/nutrition/item/buff/event_trigger/event_outcome）统一提供 i18n key，并保留 `name`/`desc` 兜底文本。
- 持续效果请显式给出 `*st` 与 `*sr`，避免默认行为歧义。
- 对 `*_max2` 谨慎使用，指数增长容易导致数值失控。
- 新增展示文案时同步提供 `lang/zh_cn.json` 与 `lang/en_us.json`，避免只在单语言下可见。
- food/item 中引用的 nutrition id 应与 `nutrition/*.json` 保持一致，避免运行时被忽略。
- 如为 buff/item/trigger/outcome 准备图标，使用 `icon_base64` 字段嵌入 PNG 图标，增强 UI 展示效果。
- Buff 如需在桌宠窗口状态栏中显示图标，请同时设置 `icon_base64` 和 `display_in_status_bar: true`。

---

## 20. 兼容建议

- 每次发版更新 `version`，并维护简单变更日志。
- 如需依赖其他 mod，使用 `requires` 明确声明。
- 与已知重做同类内容的 mod 填入 `conflicts`。

---

## 21. 最小可运行示例（区间 buff）

下面给出一个可直接复制的最小示例，演示状态区间 buff 的两种写法：

- 数值区间：`min/max`
- 百分比区间：`percent_min/percent_max`

### 目录结构

```text
mod/demo.threshold/
├─ pack_info.json
├─ status/
│  └─ status.json
└─ buff/
   └─ status/
      └─ status_buffs.json
```

### pack_info.json

```json
{
  "id": "demo.threshold",
  "name": "Threshold Demo",
  "version": "0.1.0"
}
```

### status/status.json

仅示意 `energy`：

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

### buff/status/status_buffs.json

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

### 行为说明

- `strong`：当 `800 ≤ energy < 1200` 时激活，离开区间自动移除。
- `exhausted`：当 `10% ≤ energy/base_max×100 < 20%` 时激活，离开区间自动移除。

---

## 22. icon_base64 图标系统

`icon_base64` 是一个可选字段，允许为实体（buff / item / event_trigger / event_outcome）提供图标。图标以 **Base64 编码的 PNG 图片** 形式嵌入 JSON 中，在详情弹窗的顶栏中展示。

### 支持 icon_base64 的实体类型

| 实体类型 | 字段位置 | 展示位置 |
|----------|----------|----------|
| buff | buff JSON 记录中 | buff 详情弹窗 + （可选）桌宠 buff 图标栏 |
| item | item JSON 记录中 | 物品详情弹窗 |
| event_trigger | event_trigger JSON 记录中 | 事件详情弹窗 |
| event_outcome | event_outcome JSON 记录中 | 事件结果详情弹窗 |

### 如何生成 icon_base64

将 PNG 图片文件转换为 Base64 字符串。可使用以下方法：

**Python：**
```python
import base64
with open("icon.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode("utf-8")
print(b64)  # 复制此字符串到 JSON 中
```

**命令行（Linux/macOS）：**
```bash
base64 -w0 icon.png
```

### 示例（buff）

```json
{
  "id": "coffee_focus",
  "name": "咖啡专注",
  "icon_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "display_in_status_bar": true,
  "energys": -1,
  "energyst": 12,
  "energysr": "refresh"
}
```

### display_in_status_bar（仅 buff）

buff 专属字段，控制是否在桌宠窗口的 buff 图标栏中显示图标。当 buff 激活且此字段为 `true` 时，buff 图标会出现在桌宠窗口的状态栏中。

```json
{
  "id": "well_fed",
  "name": "饱食",
  "icon_base64": "...",
  "display_in_status_bar": true
}
```

> **注意**：`display_in_status_bar` 需要同时提供 `icon_base64` 才有效。如果 buff 超过 3 个，图标栏会自动折叠为 `...` 溢出指示器，鼠标悬停可查看全部 buff 列表。

---

## 23. 快速验证步骤

1. 放置示例目录后启动程序。
2. 在调试窗口将体力设为 `900`，确认 `strong` 生效（力量 +4）。
3. 将体力设为 `150`（基础上限 1000 的 15%），确认 `exhausted` 生效（力量/敏捷 −2）。
4. 将体力设为 `250`，确认 `exhausted` 自动移除。
5. 查看日志，确认无 schema error。

---

## 24. 常见错误排查

### 1) 百分比区间写成 0\~1 导致不生效

- **错误**：`percent_min: 0.1, percent_max: 0.2`
- **正确**：`percent_min: 10, percent_max: 20`
- **原因**：百分比区间单位是 `0~100`，不是 `0~1`。

### 2) 区间边界理解错误

- 系统使用**左闭右开**：`[min, max)`。
- 例如 `min=800, max=1200`：命中 `800 ≤ value < 1200`，`1200` 不命中。
- 百分比区间同理：`percent_min ≤ percent < percent_max`。

### 3) 百分比基准用错

- 状态百分比基准：`当前状态值 / 该状态基础上限(max) × 100`
- 营养百分比基准：`当前营养值 / 该营养基础上限(max) × 100`
- 注意：这里是"基础上限"，不是实时修正后的上限。

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
- 检查是否被 `requires`/`conflicts`/`requires_versions` 拦截。
- 查看日志中 `[Mod]` 前缀的输出，确认 mod 是否被扫描和加载。
- 每次 mod 加载后，日志会显示 `新增/修改/删除` 的 ID 列表，用于验证 mod 对注册表的预期变更。
- 若 mod 被延迟加载，日志会输出 `[Mod]延迟加载: {id} (前置 [...] 未就绪)`；若后续重试成功则有 `[Mod]重试成功: {id}`。

### 8) 前置 mod 未满足导致 mod 被放弃

- 检查日志中是否包含 `[Mod]放弃 {id}: 前置mod未满足` 的输出。
- 确认被引用的前置 mod 的 `id` 拼写完全一致（区分大小写）。
- 确认前置 mod 的 `pack_info.json` 有效且没有校验问题。
- 前置 mod 可以被其他 mod、基础模块或本 mod 自身提供，确保其在扫描范围内。
- mod 的加载顺序不影响依赖解析：前置 mod 即使排在后面，当前 mod 也会被推迟等待加载。

### 9) 快速自检清单

按顺序检查：

1. `pack_info.json` 是否可解析且字段齐全。
2. `status/nutrition` 区间字段是否使用正确单位与边界。
3. `buff_id` 是否存在于已加载 buff 注册表。
4. 调试窗口中状态值是否确实进入目标区间。
5. 日志中是否出现 schema error/warn 与依赖冲突提示。

---

## 25. 后续扩展建议

- 若 mod 需要接入未来新增资源类型，优先遵循统一资源钩子协议，而不是绕过 `LifeModRegistry` 直接改全局状态。
- 资源装配应满足"可加载、可回滚、可诊断"三项要求，避免产生半加载状态。
