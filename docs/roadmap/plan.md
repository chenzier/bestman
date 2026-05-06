# 计划系统 技术路线

> 版本：v1.2（已完成）

---

## 功能

| 功能 | 命令 | 状态 |
|------|------|------|
| 计划创建 | `bestman plan create` | ✅ |
| 计划查看 | `bestman plan show` | ✅ |
| 计划编辑 | `bestman plan edit` | ✅ |
| 周回顾 | `bestman review` | ✅ |
| 计划自适应 | `bestman talk` 中修改，到期自动恢复 | ✅ |

---

## 计划创建流程

交互式 CLI 收集以下信息：

- **目标类型**：weight_loss / muscle_gain / habit / custom
- **起始体重**（可选）
- **目标体重**（可选）
- **总天数**（默认 120）
- **健身水平**：beginner / occasional / intermediate
- **偏好**：bodyweight / outdoor / mixed

LLM 基于以上信息生成分阶段计划和里程碑，保存为 `~/.bestman/plan.yaml`。

---

## 计划结构

```yaml
name: <plan name>
goal_type: weight_loss|muscle_gain|habit|custom
start_date: YYYY-MM-DD
target_date: YYYY-MM-DD
total_days: <int>
profile:
  height_cm: <float | None>
  start_weight_kg: <float | None>
  target_weight_kg: <float | None>
  fitness_level: beginner|occasional|intermediate
  preference: bodyweight|outdoor|mixed
stages:
  - { name: ..., days: [start, end], daily_task: ... }
milestones:
  <day>: "<name>"
```

---

## 计划自适应

通过 `bestman talk` 与船长对话，可临时调整训练计划。调整记录存入 `plan_overrides` 表，到期自动恢复。

```sql
CREATE TABLE plan_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_date TEXT NOT NULL,
    expires_date TEXT,
    field TEXT NOT NULL,
    original_value TEXT NOT NULL,
    override_value TEXT NOT NULL,
    reason TEXT DEFAULT '',
    active INTEGER DEFAULT 1
)
```

---

## 已知缺口

- 身高（`height_cm`）未在 CLI `plan_create` 中提示输入
- 体重目标未和 `weigh` 结果联动做自动适应（目前仅手工调整）
