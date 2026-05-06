# 健身/体重 技术路线

> 版本：v1.2（已完成基础）

---

## 功能

| 功能 | 命令 | 状态 |
|------|------|------|
| 记录体重 | `bestman weigh <kg>` | ✅ |
| 体重趋势 | `bestman progress` | ✅ |
| 计划目标联动 | plan.yaml target_weight | ✅ |
| 队长动作指导 | `bestman talk`（船长职责） | ✅ |
| 队医反馈 | 体重变化时队医发言 | 📋 待实现 |
| 伤病咨询 | `bestman talk`（队医角色） | 📋 待实现 |

---

## bestman weigh

```
$ bestman weigh 72.5
⚖️ 体重记录
当前：72.5 kg  ↓ -0.3 kg（距上次）
距目标还有 4.5 kg
[导航员] 稳步下降，这个节奏很健康。继续吃好练好。
```

### 数据表

```sql
CREATE TABLE weights (
    date TEXT PRIMARY KEY,
    weight_kg REAL NOT NULL,
    note TEXT DEFAULT ''
)
```

### LLM 评论

```python
def weigh_comment(client, current_weight, prev_weight,
                  target_weight, trend_description):
    """1-2 句话，用航海意象评论趋势和健康程度。"""
```

---

## bestman progress

显示最近 4 次体重的 ASCII 柱状图 + 周均减重 + 预计达标日期。

```
📊 体重变化趋势

  72.7 ██████████
  72.5 █████████
  72.3 ████████
  71.9 ███████

  周均减重：0.27 kg/周 ↓
  预计达标：2026-06-15
```

---

## 待实现

### 队医集成

队医上船后，体重记录触发队医发言：

- `weight_loss` → 队医评论（健康评估）
- `weight_gain` → 队医关心（排查原因）
- `weight_plateau` → 队医建议（打破平台期）

### 伤病咨询

`bestman talk` 时若用户提及身体不适（关键词检测），自动切换队医角色对话：

```
你> 膝盖弯下去有点疼
队医（张叔）：具体哪个位置？膝盖骨下面还是两侧？
你> 正下面
队医（张叔）：髌腱炎的可能。这几天把深蹲换成靠墙静蹲，
              角度不要超过 90 度。我给你调一下计划。
              （计划已更新：深蹲 → 靠墙静蹲，7 天后恢复）
```

### 体态记录（远期）

- `bestman photo` — 定期拍体态照片做对比
- 不做 AI 分析，仅做时间轴对比展示
