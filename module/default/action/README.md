# action 目录

此目录存放**动作（Action）定义**，动作是桌宠播放的帧动画，用于表现各种状态和行为（如睡眠、濒死、死亡、待机等）。

## 目录结构

- `default_builtin.json` - 内置动作定义（睡眠、濒死、死亡等）
- `vanilla.json` - 原版动画占位文件（原版动画在代码中硬编码注册，无需在此定义）

## JSON 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 唯一动作 ID，不能以 `vanilla.` 开头 |
| `name` | string | 否 | 可读动作名称 |
| `desc` | string | 否 | 动作描述 |
| `image_base64` | array\<string\> | 是 | 帧图像列表（非空），支持 `@KEY` 资源引用 |
| `frames` | number | 否 | 实际播放帧数（不大于 image_base64 长度，不指定则使用全部） |
| `play_mode` | string | 否 | 播放模式：`"once"`（一次播放）/ `"loop"`（循环）/ `"random"`（概率触发），默认 `"once"` |
| `random_per` | number | 仅 random | random 模式的触发概率（0 < random_per <= 100） |
| `block_mode` | string | 否 | 阻塞模式：`"exclusive"`（独占）/ `"sequence"`（序列）/ `"normal"`（普通），默认 `"normal"` |
| `frame_interval_ms` | number | 否 | 帧间隔毫秒数，默认由 ActionSystem 设定 |
| `animation_sorting` | array\<number\> | 否 | 自定义帧播放顺序（索引数组） |

### 字段详解

- **play_mode**:
  - `once`：动作播放一次后自动结束
  - `loop`：动作循环播放，直到外部停止
  - `random`：每秒按 `random_per` 概率触发一次播放，播放完毕后继续概率检查

- **block_mode**:
  - `exclusive`：独占模式，播放时暂停自动行走，停止其他所有动作；结束后恢复
  - `sequence`：序列模式，多个动作按队列顺序依次播放
  - `normal`：普通模式，仅在无独占/序列动作时播放，可被待机动画覆盖

- **image_base64** 支持资源引用：使用 `@KEY_NAME` 格式引用资源包中定义的图像，系统会自动查找并解析为 base64 数据。例如 `@DIE_PNG`、`@SLEEP_PNG`。

## 示例

```json
[
  {
    "id": "action.sleep",
    "name": "睡眠",
    "desc": "角色进入睡眠状态，快速恢复精神与体力。",
    "image_base64": ["@SLEEP_PNG", "@SLEEP2_PNG"],
    "frames": 2,
    "play_mode": "loop",
    "block_mode": "exclusive"
  },
  {
    "id": "action.dying",
    "name": "濒死",
    "desc": "生命体征微弱，角色处于濒死状态。",
    "image_base64": ["@DYING_PNG"],
    "play_mode": "once",
    "block_mode": "exclusive"
  },
  {
    "id": "action.die",
    "name": "死亡",
    "desc": "生命体征已消失，角色进入死亡状态。",
    "image_base64": ["@DIE_PNG"],
    "play_mode": "once",
    "block_mode": "exclusive"
  }
]
```

## 与 Life 模块的绑定

动作通过 buff / item 定义中的 `action_id` 字段与 Life 系统关联：

```json
{
  "id": "sleep",
  "action_id": "action.sleep",
  "auto_trigger_action": true
}
```

- 当 buff 被应用时，自动触发绑定的动作
- `auto_trigger_action: false` 时，动作不会在 buff 应用时自动触发（但可通过代码手动触发）
- 1 帧 once+exclusive 动作（如 `action.die`、`action.dying`）播放后会保持独占锁定，直到外部调用 `stop_action` 清理

## 使用建议

- 使用 `@KEY` 引用资源图像，不要直接内嵌 base64 数据（除非图像仅在单个动作中使用）
- 静态状态（如死亡、濒死）使用 `play_mode: "once"` + `block_mode: "exclusive"` + 1 帧
- 循环动画（如睡眠）使用 `play_mode: "loop"` + `block_mode: "exclusive"`
- 动作 ID 使用 `action.` 前缀命名空间，避免与其他注册表（buff、item）冲突
- 注意在资源包（如 `艾罗.json`）中定义所有 `@KEY` 引用的图像，否则动作将注册失败
