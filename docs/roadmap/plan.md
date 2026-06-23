# 训练计划技术路线

> 优先级：v2 已完成  
> 定位：支撑今日任务，不压过宠物船

## 新定位

训练计划的价值是让 TUI 中的“今日任务”可靠、清晰、可调整。

短期不要恢复早期 prototype 的完整 plan/review 系统。当前 `talk` 已作为只读船长聊天迁回；计划系统仍先做本地、轻量、可解释的计划。

## v1 必要能力

- `init --daily-task` 写入默认每日任务。
- TUI 直接展示今日任务。
- `done` 明确记录本次完成级别和用户 message。
- 同日重复打卡策略明确：
  - 禁止重复，或
  - 允许补记但不重复发奖励。

## v2 已落地计划模型

已事件化：

```text
PlanCreated
PlanAdjusted
```

projection 中保留当前计划和今日任务：

```text
plan_goal
plan_tasks
daily_task
```

CLI：

```text
bestman plan create --goal <goal> --tasks "A,B"
bestman plan show
bestman plan set-today "<task>"
```

基础字段：

```toml
[voyage]
total_days = 120
daily_task = "深蹲 3x15 + 平板支撑 3x30s"
rest_days = ["sun"]
```

后续仍可扩展：

```text
plan_id
goal_type
stages
scheduled_tasks
temporary_overrides
```

## LLM 接入边界

LLM 可以：

- 根据用户目标生成计划建议。
- 把计划解释得更温柔。
- 为伤病/疲劳提供低风险替代建议。

LLM 不应：

- 自动改规则状态。
- 在没有用户确认时改计划。
- 做医疗诊断。

## 暂缓

- 周回顾自动总结。
- 复杂分阶段 plan.yaml。
- `talk` 中直接自动修改计划。
- 体重目标自动调整训练计划。
