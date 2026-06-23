# bestman 技术路线

> 最后更新：2026-06-23  
> 当前主线：Rust-first / 宠物船-first

bestman 当前主入口是仓库根目录的 Rust 实现 `bestman`。旧 Python 版保留为 legacy/prototype 参考，不再作为新功能主线。

技术路线已按当前方向重写，见 [roadmap/](roadmap/)：

| 文档 | 内容 |
|------|------|
| [roadmap/README.md](roadmap/README.md) | 总览、架构、版本阶段、关键设计决策 |
| [roadmap/pet-vessel.md](roadmap/pet-vessel.md) | 宠物船核心：状态、动画、资产、TUI 主体验 |
| [roadmap/map.md](roadmap/map.md) | 地图/航线：长期进度背景，不再是主玩法 |
| [roadmap/plan.md](roadmap/plan.md) | 训练计划：先做轻量本地计划，再接 LLM |
| [roadmap/fitness.md](roadmap/fitness.md) | 健身/体重：记录、趋势、伤病建议的边界 |
| [roadmap/diet.md](roadmap/diet.md) | 饮食：非审判式记录，后置扩展 |
| [roadmap/crew.md](roadmap/crew.md) | 船员/角色：降级为远期叙事扩展 |
| [roadmap/other.md](roadmap/other.md) | LLM、工坊、社区、发布等 backlog |

当前短期目标：

1. Rust CLI/TUI 成为唯一推荐入口。
2. 宠物船体验达到日常可用：打卡反馈、退出可靠、图片/文本 fallback 稳定。
3. 事件源 + SQLite 投影保持为核心数据架构。
4. LLM 只生成叙事，不参与规则状态变更。
5. Python 版停止并行扩新功能。
