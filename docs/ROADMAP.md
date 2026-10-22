# bestman 技术路线

> 最后更新：2026-10-22
> 当前实现：Rust CLI/TUI；下一阶段：基于 Arxd 的 Android Agent 化宠物船

bestman 当前主入口是仓库根目录的 Rust 实现 `bestman`。早期 Python prototype 已从主线代码中移除；历史方案保留在 `docs/superpowers/` 和 git 历史中。

技术路线已按当前方向重写，见 [roadmap/](roadmap/)：

| 文档 | 内容 |
|------|------|
| [roadmap/README.md](roadmap/README.md) | 总览、架构、版本阶段、关键设计决策 |
| [roadmap/pet-vessel.md](roadmap/pet-vessel.md) | 宠物船核心：状态、动画、catalog、多船收集 |
| [roadmap/map.md](roadmap/map.md) | 地图/航线：长期进度背景，不再是主玩法 |
| [roadmap/plan.md](roadmap/plan.md) | 训练计划：先做轻量本地计划，再接 LLM |
| [roadmap/fitness.md](roadmap/fitness.md) | 健身/体重：记录、趋势、伤病建议的边界 |
| [roadmap/diet.md](roadmap/diet.md) | 饮食：非审判式记录，后置扩展 |
| [roadmap/mobile.md](roadmap/mobile.md) | Android 手机版：Agent 底座、宠物船对话界面与阶段验收 |
| [roadmap/crew.md](roadmap/crew.md) | 船长、吟游诗人等对话角色；复杂船员养成后置 |
| [roadmap/other.md](roadmap/other.md) | LLM、工坊、社区、发布等 backlog |

当前基础与后续方向：

1. 现有 Rust CLI/TUI 保持可用，v3.0-v3.6 叙事和健康基础能力已落地。
2. Android 首版以 Arxd 为候选宿主，复用模型连接、流式对话、持久化与任务恢复；先 fork 验证，不以抽离独立 Agent core、MCP 或 Rust 手机移植为前置条件。
3. 船长、吟游诗人等角色通过 Agent 与用户对话；宠物船界面呈现台词、表情和动画，先验证角色体验与重启恢复。
4. 后续真实打卡、计划和体重记录接入现有 Rust 规则与事件语义；Agent 可以提出建议，但不能直接修改奖励或事实记录。移动端存储与桥接方案待验证。
5. AI 计划和拍照饮食在角色对话体验成立后推进；份量与热量是可修正的估算。
6. 地图主玩法、复杂船员养成、主题市场和社区后置。
