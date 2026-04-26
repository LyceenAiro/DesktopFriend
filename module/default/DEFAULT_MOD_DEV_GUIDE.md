# Default 模组开发手册

## 概述

Default 模组系统是独立于 Life 模组系统的基础功能扩展，目前支持：
- **动作注册**：通过 JSON 文件注册自定义动画动作
- **资源包覆盖**：通过 `resources/` 目录注入资源包键值对

动作系统独立于养成模块运行，所有动作通过 `ActionSystem` 单例管理。

## 目录结构

一个 default 模组的目录结构如下：

```
mod/<mod_id>/
  pack_info.json          # Mod 元信息（必需，若无则仅扫描 action/ 和 resources/）
  action/                 # 动作 JSON 定义（可选）
    *.json
  resources/              # 资源包覆盖（可选）
    *.json
```

### pack_info.json

```json
{
  "id": "example.action_mod",
  "name": "示例动作模组",
  "version": "1.0.0",
  "description": "一个示例动作模组",
  "requires": [],
  "requires_resource_pack": "LyceenAiro",
  "min_protocol": "0.3",
  "max_protocol": "0.3"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | Mod 唯一标识，必须与目录名一致 |
| `name` | string | 否 | 显示名称 |
| `version` | string | 否 | 版本号 |
| `description` | string | 否 | 描述 |
| `requires` | list[string] | 否 | 依赖的其他 mod id |
| `requires_resource_pack` | string | 否 | 需要的资源包名称（不匹配时跳过加载） |
| `min_protocol` / `max_protocol` | string | 否 | 协议版本约束 |

## 动作注册

### 动作 JSON 格式

在 `action/` 目录下放置任意数量的 JSON 文件，每个文件包含一个动作定义列表：

```json
[
  {
    "id": "custom.wave",
    "name": "挥手",
    "desc": "角色挥手打招呼",
    "image_base64": ["@WAVE1_PNG", "@WAVE2_PNG", "@WAVE3_PNG"],
    "animation_sorting": [0, 1, 2, 1, 0],
    "frame_interval_ms": 200,
    "play_mode": "once",
    "block_mode": "normal"
  },
  {
    "id": "custom.dance",
    "name": "跳舞",
    "desc": "随机触发的跳舞动画",
    "image_base64": ["@DANCE1_PNG", "@DANCE2_PNG"],
    "frames": 2,
    "frame_interval_ms": 180,
    "play_mode": "random",
    "random_per": 5.0,
    "block_mode": "normal"
  }
]
```

### 注册字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 动作唯一标识，不能以 `vanilla.` 开头 |
| `name` | string | 否 | 显示名称（缺省取 id） |
| `desc` | string | 否 | 描述 |
| `image_base64` | list[string] | 是 | base64 图像列表，支持 `@KEY` 引用资源包 |
| `frames` | int | 否 | 帧数（1=静态），缺省取 1 |
| `animation_sorting` | list[int] | 否 | 帧索引排序，若填写则忽略 `frames` |
| `frame_interval_ms` | int | 否 | 帧间隔毫秒，缺省取待机动画间隔 |
| `play_mode` | string | 是 | `"once"` / `"loop"` / `"random"` |
| `random_per` | float | 否 | 概率 0-100（random 模式必填；0 注册失败；100 自动转 loop） |
| `block_mode` | string | 否 | `"exclusive"` / `"sequence"` / `"normal"`，缺省 `"normal"` |

### 字段详解

#### image_base64

存储动画帧的 base64 编码图像列表。有两种使用方式：

1. **直接 base64 数据**：将 PNG/其他格式图像编码为 base64 字符串放入列表
2. **`@KEY` 引用**：在字符串前加 `@` 前缀引用资源包中的图像 key

例如，`@DEFAULT_PNG` 会引用当前资源包中的 `DEFAULT_PNG` 键对应的图像。

#### frames（帧数）与 animation_sorting（帧排序）

两种指定动画帧序列的方式：

- **frames**：从 `image_base64` 列表的开头取指定数量的图像作为动画帧。例如 `image_base64` 有 5 张图，`frames: 3` 则取前 3 张组成动画。
- **animation_sorting**：提供索引排序列表，例如 `[0, 1, 2, 3, 2, 1]`，动画会按此索引序列播放帧。这样可以重复利用图像资源。

两者都提供时，`animation_sorting` 优先。如果 `image_base64` 中的资源数量少于需求，注册会失败。

#### play_mode（播放方式）

| 值 | 说明 |
|------|------|
| `once` | 调用时动画播放一次即停止 |
| `loop` | 在调用结束前一直循环播放动画 |
| `random` | 未触发时每秒进行概率检查，触发后播放一轮动画，结束后继续概率检查 |

**random 模式的概率检查**：
- 配置 `random_per` 设定触发概率（0 < value ≤ 100）
- 每秒进行一次概率判定
- 触发后播放一轮帧动画，然后继续概率检查
- `random_per = 100` 会自动转为 loop 模式

#### block_mode（封锁选项）

| 值 | 说明 |
|------|------|
| `exclusive` | 独占模式。触发时让其他动画全部忽略，停止自动行走模块，序列模式的动画也不会触发。多个独占则使用最新的 |
| `sequence` | 序列模式。多个序列动画可同时排队，按顺序播放。仅支持 `once` 和 `random` 播放模式。序列播放中、队列还有排队动画时，原版动画不可触发，自动行走停止 |
| `normal` | 普通模式（默认）。触发时替换待机动画，结束后恢复待机。有独占或序列播放时暂停等待。不影响自动行走模块 |

## 资源包覆盖

通过 `resources/` 目录下的 JSON 文件，可以为当前资源包注入额外的 key-value 对：

```json
{
  "WAVE1_PNG": "/9j/4AAQ...base64数据...",
  "WAVE2_PNG": "/9j/4AAQ...base64数据...",
  "DANCE1_PNG": "/9j/4AAQ...base64数据..."
}
```

这些 key 可以在动作 JSON 中通过 `@KEY` 引用。

## 在 Life 模组中绑定动作

在 Life 模组的 JSON 定义中，可以通过 `action_id` 字段绑定动作：

### Buff 绑定动作

```json
{
  "id": "buff.dance_fever",
  "name": "跳舞热",
  "action_id": "custom.dance",
  "status": ["happy", "energy"],
  "happy": 5,
  "energy": -3,
  "happy_s": 2,
  "happy_st": 10
}
```

- `once` 模式：buff 生效时触发一次
- `loop` / `random` 模式：buff 持续期间动画持续播放
- buff 过期时动画自动停止

### 物品绑定动作

```json
{
  "id": "item.wave_wand",
  "name": "挥手魔杖",
  "action_id": "custom.wave",
  "usable": true,
  "consumable": true
}
```

- `once` 模式：使用物品时触发一次
- `loop` 模式：仅播放一轮后自动停止
- `random` 模式：可能只进行一次概率检查

### 事件触发器绑定动作

```json
{
  "id": "trigger.dance_event",
  "name": "舞会",
  "action_id": "custom.dance",
  "duration_s": 10
}
```

- 有持续时间的触发器：动画在触发期间持续播放
- 无持续时间的触发器：触发时播放一次

### 事件结果绑定动作

```json
{
  "id": "outcome.dance_result",
  "name": "跳舞结果",
  "action_id": "custom.dance"
}
```

- 执行事件结果时触发动作

## 常见问题

### Q: 动作注册失败，日志显示 "id 不能以 'vanilla.' 开头"
A: `vanilla.` 前缀保留给原版动画，自定义动作请使用其他前缀，如 `custom.`。

### Q: 动画为什么不播放？
A: 可能的原因：
1. 动作未注册：检查 `image_base64` 中的图像引用是否正确
2. 资源包引用无效：检查 `@KEY` 引用的 key 是否存在于资源包中
3. `block_mode` 冲突：独占动作播放时会阻止其他动作

### Q: 如何测试自定义动作？
A: 在设置 → 调试标签页中，使用"动作选择器"下拉框选择动作，点击"触发"按钮测试。

### Q: `requires_resource_pack` 验证失败？
A: 确保当前使用的资源包名称与 `requires_resource_pack` 指定的名称一致。资源包名称通常是文件名（不含扩展名）。
