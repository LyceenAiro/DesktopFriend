# level 目录

此目录存放**等级系统配置**，定义宠物如何升级以及升级所需的经验和奖励。

## JSON 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `initial_exp_required` | number | 升至 2 级所需的初始经验值 |
| `passive_exp_per_tick` | number | 每 tick 被动获得的经验值 |
| `growth_ranges` | list\<dict\> | 不同等级区间的升级经验增长规则 |

## 升级经验增长规则 (growth_ranges)

| 字段 | 类型 | 说明 |
|---|---|---|
| `from_level` | number | 规则应用的起始等级（包含） |
| `to_level` | number | 规则应用的结束等级（包含） |
| `exp_growth` | number | 该等级段的经验要求，通常随等级递增 |

## 示例

```json
{
  "initial_exp_required": 20.0,
  "passive_exp_per_tick": 0.01,
  "growth_ranges": [
    {"from_level": 1, "to_level": 10, "exp_growth": 20.0},
    {"from_level": 11, "to_level": 20, "exp_growth": 100.0},
    {"from_level": 21, "to_level": 30, "exp_growth": 500.0}
  ]
}
```

## 使用建议

- `initial_exp_required` 应设置为较小的值，让玩家尽快升到 2 级
- `passive_exp_per_tick` 是主要的经验获取来源，结合 tick 间隔（默认 1 秒）计算每小时的被动经验
- `growth_ranges` 应该按 `from_level` 从小到大排序，无需覆盖所有等级（规则递推）
- 后期等级的 `exp_growth` 应该明显高于早期，形成清晰的进度压力
- 使用等级段而非单个等级，便于批量调整经验曲线

## 经验计算示例

假设默认配置：
- 初始升级：1→2 级需要 20 经验
- 1-10 级：每级需要 20 经验
- 11-20 级：每级需要 100 经验
- 21+ 级：每级需要 500 经验

使用 `passive_exp_per_tick = 0.01`，每秒获得 0.01 经验：
- 升到 2 级：20 ÷ 0.01 = 2000 秒 ≈ 33 分钟
- 升到 10 级：(20 + 8×20) ÷ 0.01 ≈ 2.5 小时
- 升到 20 级：需要更长时间，创造持续目标感
