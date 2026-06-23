# bestman 技术路线

> 最后更新：2026-06-23  
> 当前主线：Rust-first / LLM narrative + plan next

bestman 当前主入口是仓库根目录的 Rust 实现 `bestman`。旧 Python 版保留为 legacy/prototype 参考，不再作为新功能主线。

技术路线已按当前方向重写，见 [roadmap/](roadmap/)：

| 文档 | 内容 |
|------|------|
| [roadmap/README.md](roadmap/README.md) | 总览、架构、版本阶段、关键设计决策 |
| [roadmap/pet-vessel.md](roadmap/pet-vessel.md) | 宠物船核心：状态、动画、catalog、多船收集 |
| [roadmap/map.md](roadmap/map.md) | 地图/航线：长期进度背景，不再是主玩法 |
| [roadmap/plan.md](roadmap/plan.md) | 训练计划：先做轻量本地计划，再接 LLM |
| [roadmap/fitness.md](roadmap/fitness.md) | 健身/体重：记录、趋势、伤病建议的边界 |
| [roadmap/diet.md](roadmap/diet.md) | 饮食：非审判式记录，后置扩展 |
| [roadmap/crew.md](roadmap/crew.md) | 船员/角色：降级为远期叙事扩展 |
| [roadmap/other.md](roadmap/other.md) | LLM、工坊、社区、发布等 backlog |

当前短期目标：

1. v2.0 训练计划与真实 LLM 叙事。
2. LLM 只生成日志、总结和温柔反馈，不改状态。
3. 本地轻量训练计划先落地，再接 LLM 建议。
4. 事件源 + SQLite 投影保持为核心数据架构。
5. 地图、船员、主题市场和社区全部后置。
