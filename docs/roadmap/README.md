# bestman 技术路线 · 总览

> 最后更新：2026-06-23  
> 当前阶段：Rust v0.1 prototype，准备进入 v1 可用主线

## 产品定位

bestman 的核心体验是 **宠物船陪伴 + 健身打卡**。

```text
每天训练打卡 -> 宠物船状态变化 -> 航线进度推进 -> 航海日志与奖励
```

这不是一个以地图探索为主的航海游戏。地图只承担长期进度可视化，宠物船才是用户每天打开时的注意力中心。

## 当前架构

```text
Rust CLI/TUI
  ├── rules.rs             # 规则系统：打卡、休息、购买、换船
  ├── events.rs            # append-only events.jsonl
  ├── projection.rs        # SQLite 当前状态投影
  ├── vessels/             # vessel manifest / spritesheet / frame cache
  ├── tui.rs               # 宠物船终端界面
  ├── dashboard.rs         # dashboard PNG / 动画帧导出
  ├── terminal_image.rs    # Kitty 图片协议
  └── llm.rs               # 当前为 mock narrative
```

运行时数据：

```text
<home>/
  config.toml
  events.jsonl
  bestman.db
  cache/
  vessels/
```

## 当前已落地

| 能力 | 状态 |
|------|------|
| Rust CLI 主入口 | 已落地 |
| 初始化 / 状态 / 打卡 / 休息 / 日志 | 已落地 |
| event source + SQLite projection | 已落地 |
| mock LLM 航海日志 | 已落地 |
| 默认宠物船 `starter_sloop` | 已落地 |
| spritesheet + manifest 船只资产 | 已落地 |
| 用户自定义 vessel 目录 | 已落地 |
| 静态 TUI / live TUI | 已落地 |
| Kitty 图片帧输出 | 已落地，有文本 fallback |
| PNG preview / dashboard / frame export | 已落地 |
| 今日任务展示 | 已落地 |
| 同日重复打卡保护 | 已落地 |
| 打卡即时反馈 | 已落地 |
| `bestman` 二进制入口 | 已落地 |
| Rust 测试 | 已落地 |

## 版本阶段

### v0.1 — Rust 原型闭环（已完成）

目标：证明新架构可行。

- Rust core
- event source + SQLite projection
- starter vessel
- TUI/PNG 输出
- mock LLM 日志
- 基础商店/换船
- 自动化测试覆盖核心路径

### v1.0 — 日常可用主入口

目标：用户能每天用它打卡，不需要理解内部实现。

- 发布可执行二进制，减少 `cargo run` 依赖
- `bestman` 命令指向 Rust 版
- TUI 首屏聚焦宠物船和今日任务
- 同日重复打卡策略明确
- 打卡后即时反馈：进度、金币、心情、日志
- 图片模式稳定定位，纯文本 fallback 保持完整可用
- 错误提示产品化，不暴露内部路径和 debug 信息
- README / roadmap / legacy 文档持续对齐

### v1.1 — 宠物船体验强化

目标：船像宠物，而不是状态图标。

- 船只状态机细化：waiting / sailing / happy / resting / low_energy / treasure
- 不同状态有明确动画和文案反馈
- 互动反馈：鼓励、休息提醒、连续打卡 callback
- 打卡历史影响船只表现，但不制造焦虑
- dashboard PNG 与 TUI 视觉语言统一

### v1.2 — 船只资产与商店

目标：允许多船、多皮肤、可扩展资产。

- ownership / equipped 模型
- shop item 类型：船、皮肤、装饰、动画
- vessel manifest 扩展 rarity / price / unlock
- 自定义船只校验和导入体验
- 后续预留 LLM 生成 spritesheet 草稿，但规则和资产校验仍在本地

### v2.0 — 训练计划与真实 LLM 叙事

目标：让打卡内容更贴合用户目标。

- 本地轻量训练计划
- 今日任务在 TUI 中展示
- LLM 只生成日志、总结、温柔反馈
- LLM 失败时 template fallback
- 保存 provider/model/prompt version
- 不允许 LLM 改状态：position/coins/mood/trust 仍由 rules 决定

### v3.0 — 远期叙事扩展

目标：在宠物船体验稳定后，再加入更复杂的世界观。

- 船员/角色作为叙事扩展，而不是核心养成
- 饮食、体重、伤病建议作为可选模块
- 地图动态效果、创意工坊、社区资产市场
- 里程碑史诗和长期回顾

## 关键设计决策

1. **Rust 是主入口**：Python 版是 legacy/prototype，不并行扩新功能。
2. **宠物船优先**：地图是背景，船是每日体验中心。
3. **规则拥有状态**：金币、心情、信任、位置只能由 deterministic rules 改。
4. **LLM 只写叙事**：LLM 不参与状态计算，不决定奖励。
5. **事件源是事实来源**：`events.jsonl` 是事实，SQLite 可重建。
6. **资产可校验**：船只由 manifest + spritesheet 描述，路径和帧范围必须校验。
7. **图片协议可选**：Kitty/Ghostty/WezTerm 图片模式是增强，文本 fallback 必须可用。
8. **避免焦虑型系统**：不做过重任务、惩罚、复杂 XP grind。

## 不再作为主线的旧方向

以下旧路线已降级，不应优先实现：

- Python CLI 继续扩展新功能
- 地图作为核心玩法
- 复杂船员招募/升级/任务系统
- 每周任务和 XP 数值追踪
- 大型主题市场或社区功能

这些想法可以保留为 backlog，但必须等 v1 宠物船主体验稳定后再评估。

## Python legacy 功能归类

转 Rust 后，旧 Python 功能不直接照搬。统一按三类处理：

| 旧功能 | 当前归类 | 路线位置 | 处理方式 |
|------|------|------|------|
| 真实 LLM 日志 | 必须迁回 | v2.0 / [other.md](other.md) | 只生成叙事，失败 template fallback |
| `talk` AI 教练 | 重做 | v2.0 / [plan.md](plan.md) | 先做计划建议，不让 LLM 自动改状态 |
| `plan create/show/edit` | 重做 | v2.0 / [plan.md](plan.md) | 事件化轻量计划，不照搬 `plan.yaml` 复杂体系 |
| 周回顾 AI 总结 | 暂缓 | v2/v3 / [other.md](other.md) | 等真实 LLM 稳定后再做 |
| `weigh` / `progress` | 必须迁回但后置 | v2 / [fitness.md](fitness.md) | 走事件源，保持非焦虑反馈 |
| 旧 50×14 地图主界面 | 重做 | [map.md](map.md) | 降级为长期进度背景 |
| `bestman map` / `stats` | 暂缓 | [map.md](map.md) | 先用 TUI progress 和 dashboard PNG |
| 1-6 骰子 / 互动掷骰 | 重做 | v1.1/v2 | 当前 1-3 简化节奏；后续如恢复必须服务宠物反馈 |
| `done -e N` 手动额外步数 | 暂缓 | v2 | 容易破坏规则一致性，需事件化设计 |
| dice-mode 配置 | 暂缓 | v2 | 等骰子模型稳定后再做 |
| naval / cultivation 主题 | 暂缓 | v3 | 当前只做宠物船视觉资产，不恢复全局主题系统 |
| 随机事件 | 重做 | v2/v3 | 不能抢核心打卡体验，必须 deterministic replay |
| 宝藏系统 | 重做 | v1.1/v1.2 | 保留为宠物船奖励/动画触发，不做地图主玩法 |
| skip token | 重做 | v1.1 | 当前只做 rest/skip；后续再补“休息不羞辱”的更细规则 |
| `reset` | 必须补 | v1.x | 需要安全确认，支持清空指定 `--home` 数据 |
| `config dice-mode` / 配置命令 | 暂缓 | v2 | 当前先用 `config.toml`，后续只暴露高频安全配置 |
| crew / 船员 / 港口 | 远期 | [crew.md](crew.md) | 降级为叙事扩展，不做 v1 主线 |
| `eat` 饮食记录 | 远期 | [diet.md](diet.md) | 可选非审判式记录 |
| 自定义地图 / 主题市场 / 社区 | 远期 | [other.md](other.md) | 等本地资产模型稳定后再设计 |
