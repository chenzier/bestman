# bestman 技术路线 · 总览

> 最后更新：2026-06-23  
> 当前阶段：Rust-only 主线，v3.x 叙事 backlog

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

详细阶段执行与验收标准见 [P1-P5 执行方案](p1-p5-execution-plan.md)。

## 当前已落地

| 能力 | 状态 |
|------|------|
| Rust CLI 主入口 | 已落地 |
| 初始化 / 状态 / 打卡 / 休息 / 日志 | 已落地 |
| event source + SQLite projection | 已落地 |
| mock LLM 航海日志 | 已落地 |
| 默认宠物船 `starter_sloop` | 已落地 |
| spritesheet + manifest 船只资产 | 已落地 |
| catalog 注册式船只资产 | 已落地 |
| 用户自定义 vessel experimental 注册 | 已落地 |
| 静态 TUI / live TUI | 已落地 |
| Kitty 图片帧输出 | 已落地，有文本 fallback |
| PNG preview / dashboard / frame export | 已落地 |
| 今日任务展示 | 已落地 |
| 同日重复打卡保护 | 已落地 |
| 打卡即时反馈 | 已落地 |
| `reset --yes` 开发期数据清理 | 已落地 |
| `bestman` 二进制入口 | 已落地 |
| 5 艘内置宠物船 | 已落地 |
| vessel ownership / equipped 投影 | 已落地 |
| `shop list` / `shop buy` / `vessel list` / `vessel set` | 已落地 |
| 本地轻量训练计划 | 已落地 |
| OpenAI-compatible LLM 航海日志接口 | 已落地，有 template fallback |
| `recap` 长期/周/月回顾 | 已落地，有 LLM/template fallback |
| 里程碑史诗 | 已落地，到达里程碑时自动写入日志 |
| `talk` 船长聊天 | 已落地，只生成回复不改状态 |
| `weigh` / `progress` 体重记录 | 已落地，事件源 + SQLite projection |
| `config show` / `rebuild` / `vessel validate` | 已落地 |
| Rust 测试 | 已落地 |
| Python prototype 移除 | 已落地 |

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

### v1.0 — 日常可用主入口（已完成）

目标：用户能每天用它打卡，不需要理解内部实现。

- `bestman` 命令指向 Rust 版，`cargo run` 默认运行 `bestman`。
- README / 命令说明改成 Rust 版。
- 早期 Python prototype 已移除，避免双系统并行演化。
- TUI 首屏聚焦当前宠物船和今日任务。
- 同日重复打卡/休息有明确策略。
- 打卡后即时反馈：进度、金币、心情、信任、日志。
- 图片模式失败时回退文本，不影响使用。
- `reset --yes` 支持开发期清理指定 `--home`。

### v1.1 — 宠物船体验强化（已完成）

目标：先把“当前船像宠物”这件事稳住，为 v1.2 多船收集打底。

- 当前船状态机覆盖 waiting / sailing / happy / resting / low_energy / treasure。
- 不同状态有明确动画、文案、颜色和 fallback。
- 连续休整或低心情会触发 `low_energy`，但不额外惩罚。
- 连续 7 天打卡只增强宠物反馈，不额外发金币，不做复杂 XP grind。
- dashboard 文本/PNG 与 TUI 视觉语言统一，不再暴露 image path/protocol debug。
- 不引入多船经济，不引入真实 LLM，不扩地图玩法。

### v1.2 — 多船收集系统（已完成）

目标：让 bestman 的“酷功能”成立：打卡赚金币，购买/装备不同宠物船，看到当前船明显变化。

明确范围：

- 第一版是 **纯视觉差异**：船只不提供金币、心情、航速等数值加成。
- schema 预留 `traits/effects`，但 v1.2 不启用。
- 第一批 5 艘船全部手工/硬编码资产，不接 LLM 生成。
- 基于早期 prototype 预设精神重做，不恢复全局 `naval/cultivation` 主题系统。
- TUI 首屏只显示当前船，不显示 `Fleet 1/5` 之类收集进度。

第一批内置船：

| id | 来源精神 | 定位 | rarity | price |
|------|------|------|------|------|
| `starter_sloop` | 初阶帆船 | 默认温柔小帆船 | common | 0 |
| `dragon_prow` | 龙头战船 | 更有冲击力的进阶船 | uncommon | 80 |
| `ghost_lantern` | 幽灵船 | 夜航/灯火/幽灵氛围 | rare | 140 |
| `cloudblade_skiff` | 飞剑 | 云剑小舟，不恢复修仙主题 | rare | 220 |
| `yinglong_ark` | 应龙 | 高阶幻想灵舟 | epic | 360 |

实现顺序：

1. 数据模型：catalog item、owned/equipped projection、事件类型。
2. catalog：`assets/catalog.json` 注册所有内置船。
3. 规则：购买/装备写事件，SQLite 只做投影。
4. 资产：补齐 5 艘船的 manifest、spritesheet、动画帧。
5. CLI 展示：`shop list`、`shop buy <id>`、`vessel list`、`vessel set <id>`。

架构边界：

- `vessel.json` 只管渲染：spritesheet、frame、animations。
- `catalog.json` 管收集/商店：kind、price、rarity、unlock、tags。
- 所有船必须注册 catalog 才能进入新版系统。
- 用户自定义船保留为 experimental，但必须在 `<home>/catalog.json` 注册。
- `shop` 类型系统预留 `vessel/skin/decoration/animation`，v1.2 只实现 `vessel`。
- `unlock` 字段先解析/保留，第一版只支持空条件或 `always`。

### v2.0 — 训练计划与真实 LLM 叙事（已完成）

目标：在多船收集闭环稳定后，让打卡内容更贴合用户目标。

- `plan create/show/set-today` 支持本地轻量计划。
- plan 通过事件写入，SQLite 投影当前 goal/tasks/daily_task。
- 今日任务继续在 TUI 和状态 JSON 中展示。
- OpenAI-compatible LLM 接口可生成航海日志。
- LLM 失败时保留 template fallback，不阻断打卡。
- 保存 provider/model/prompt version。
- 不允许 LLM 改状态：position/coins/mood/trust 仍由 rules 决定。

### v3.0 — 长期回顾叙事扩展（已完成）

目标：在宠物船、多船收集和 LLM 日志稳定后，先加入不影响规则状态的长期叙事。

- `recap` 根据真实数据生成长期回顾。
- recap 写入事件，可通过 SQLite projection 重建。
- recap 支持 `--llm`，失败时 template fallback。
- LLM 继续只写叙事，不改金币、位置、心情、信任或拥有状态。

### v3.1 — 里程碑史诗（已完成）

- 到达里程碑时自动生成短史诗日志。
- 史诗写入事件，可通过 SQLite projection 重建。
- 支持 LLM/template fallback。
- 继续只写叙事，不改金币、位置、心情、信任或拥有状态。

### v3.2 — 船长聊天（已完成）

- `talk <message>` 基于当前状态生成船长回复。
- 回复写入事件和日志 projection。
- 支持 LLM/template fallback。
- 只聊天和建议，不自动改计划、金币、位置、心情、信任或船只。

### v3.3 — 周/月回顾（已完成）

- `recap --period week|month|all` 支持不同回顾范围标签。
- recap 事件保存 period，可通过 SQLite projection 重建。
- 支持 LLM/template fallback。
- 继续只写叙事，不改规则状态。

### v3.4 — 体重记录与趋势（已完成）

- `weigh <kg> [--note ...]` 记录体重。
- `progress` 展示最新体重、最近记录和温和趋势。
- `WeightRecorded` 事件可通过 SQLite projection 重建。
- 不做诊断，不给高风险医疗建议。

### v3.x — 后续叙事 backlog

- 船员/角色作为叙事扩展，而不是核心养成。
- 饮食、伤病建议作为可选模块。
- 地图动态效果、创意工坊、社区资产市场。
- 更细粒度的自动回顾调度。

## 关键设计决策

1. **Rust 是唯一主入口**：早期 Python prototype 已移除，不并行扩新功能。
2. **宠物船优先**：地图是背景，船是每日体验中心。
3. **规则拥有状态**：金币、心情、信任、位置只能由 deterministic rules 改。
4. **LLM 只写叙事**：LLM 不参与状态计算，不决定奖励。
5. **事件源是事实来源**：`events.jsonl` 是事实，SQLite 可重建。
6. **资产可校验**：船只由 manifest + spritesheet 描述，路径和帧范围必须校验。
7. **图片协议可选**：Kitty/Ghostty/WezTerm 图片模式是增强，文本 fallback 必须可用。
8. **避免焦虑型系统**：不做过重任务、惩罚、复杂 XP grind。
9. **收集规则和资产分离**：`vessel.json` 管渲染，`catalog.json` 管价格、稀有度、解锁。
10. **多船先做视觉差异**：v1.2 不做船只属性加成，只预留 future traits/effects。

## 不再作为主线的旧方向

以下旧路线已降级，不应优先实现：

- 恢复 Python CLI 作为产品入口
- 地图作为核心玩法
- 复杂船员招募/升级/任务系统
- 每周任务和 XP 数值追踪
- 大型主题市场或社区功能

这些想法可以保留为 backlog，但必须等 v1 宠物船主体验稳定后再评估。

## 已移除 prototype 的功能归类

早期 Python prototype 已从主线代码中移除。旧功能不直接照搬，统一按三类处理：

| 旧功能 | 当前归类 | 路线位置 | 处理方式 |
|------|------|------|------|
| 真实 LLM 日志 | 必须迁回但后置 | v2.0 / [other.md](other.md) | v1.2 之后再接；只生成叙事，失败 template fallback |
| `talk` AI 教练 | 已迁回基础版 | v3.2 | 只聊天和建议，不让 LLM 自动改状态 |
| `plan create/show/edit` | 重做 | v2.0 / [plan.md](plan.md) | 事件化轻量计划，不照搬 `plan.yaml` 复杂体系 |
| 周回顾 AI 总结 | 暂缓 | v2/v3 / [other.md](other.md) | 等真实 LLM 稳定后再做 |
| `weigh` / `progress` | 已迁回基础版 | v3.4 / [fitness.md](fitness.md) | 走事件源，保持非焦虑反馈 |
| 旧 50×14 地图主界面 | 重做 | [map.md](map.md) | 降级为长期进度背景，不进入 v1.2 |
| `bestman map` / `stats` | 暂缓 | [map.md](map.md) | 先用 TUI progress 和 dashboard PNG |
| 1-6 骰子 / 互动掷骰 | 重做 | v1.1/v2 | 当前 1-3 简化节奏；后续如恢复必须服务宠物反馈 |
| `done -e N` 手动额外步数 | 暂缓 | v2 | 容易破坏规则一致性，需事件化设计 |
| dice-mode 配置 | 暂缓 | v2 | 等骰子模型稳定后再做 |
| naval / cultivation 主题 | 不恢复主线 | v3 backlog | v1.2 只继承旧预设精神，不恢复全局主题切换 |
| 随机事件 | 重做 | v2/v3 | 不能抢核心打卡体验，必须 deterministic replay |
| 宝藏系统 | 重做 | v1.1/v1.2 | 保留为宠物船奖励/动画触发，不做地图主玩法 |
| skip token | 重做 | v1.1 | 当前只做 rest/skip；后续再补“休息不羞辱”的更细规则 |
| `reset` | 已迁回 | v1.0 | `reset --yes` 清空指定 `--home` 数据 |
| `config dice-mode` / 配置命令 | 暂缓 | v2 | 当前先用 `config.toml`，后续只暴露高频安全配置 |
| crew / 船员 / 港口 | 远期 | [crew.md](crew.md) | 降级为叙事扩展，不做 v1 主线 |
| `eat` 饮食记录 | 远期 | [diet.md](diet.md) | 可选非审判式记录 |
| 自定义船只 | 实验入口 | v1.2 / [pet-vessel.md](pet-vessel.md) | 必须在 `<home>/catalog.json` 注册才进入系统 |
| 自定义地图 / 主题市场 / 社区 | 远期 | [other.md](other.md) | 等本地资产模型稳定后再设计 |
