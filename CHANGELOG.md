# Changelog

All notable changes to bestman will be documented in this file.

---

## v1.0.0 (2026-05-03) — 全功能航海

### 新增

**AI 航海日志** (`bestman done` 时 LLM 生成独特叙事)
- 接入 OpenAI 兼容 API，每次打卡生成独一份的航海日志
- LLM 不可用时自动退回 15 条硬编码模板，产品不崩
- 日志带阶段名、剩余天数，叙事有航海意象
- Rich spinner 加载态（仿 hermes-agent pattern）

**AI 导航员教练** (`bestman talk`)
- 对话循环模式（`bestman talk`）或单次模式（`bestman talk -m "..."`）
- 教练角色：老练的导航员，不是教官。可协商调整任务，鼓励而不施压
- 开场白根据当前航行状态自动生成
- 交互循环仿 hermes cli.py（轻量版，console.input 代替 prompt_toolkit）

**破戒防护系统** (`bestman skip`)
- 休整令牌：连续打卡 7 天自动获得一枚
- 使用令牌跳过当天但不中断连击，不推进地图
- 跳过日生成驿站叙事："船队在避风港暂歇"
- 防止破堤效应——一次例外 ≠ 全盘失败

**随机事件系统**
- 三种事件：顺风（自动+1格）、鼓励（正向叙事）、挑战（建议额外运动）
- 每格用 day 号做确定性种子，同一天永远触发同一事件
- 约 50% 每日触发率，有惊喜但不泛滥
- 事件文案从 config 读取，可自定义

**地图视觉升级**
- 尾迹效果：船后 1-3 格 `≈` 亮青色波纹
- 确定性装饰：`🐟` `⭐` 随机分布在海域，同一格永远显示一样
- 里程碑分级：刚到达的亮色 `✦`，走过的暗色 `✦`
- 迷雾变化：前方 5 格内里程碑有微弱线索提示
- 终点 `🏁` 完成标记

**架构增强**
- Schema 版本管理（v2），自动迁移旧数据库
- LLM：`llm.py` 独立模块，只暴露 `LLMClient` 和两个生成函数
- 事件：`events.py` 独立模块，`EventEngine` 从 config 读配置
- Config：`~/.bestman/.env` 加载 API key，`~/.bestman/config.yaml` 存储事件配置
- 测试：129 个，覆盖所有命令、所有事件类型、LLM 可用/不可用两条路径

### CLI 命令全景

| 命令 | 作用 |
|------|------|
| `bestman init` | 初始化航行 |
| `bestman` | 仪表盘（地图 + 连击 + 令牌 + 日志） |
| `bestman done` | 完成今日任务（LLM 日志 + 事件 + 里程碑） |
| `bestman skip` | 使用令牌跳过（保连击） |
| `bestman talk` | AI 导航员对话 |
| `bestman log` | 查看航海日志 |

---

## v0.0.1 (2026-05-03) — 最小可用原型

### 新增

**核心循环**
- `bestman init` — 初始化航行，创建 `~/.bestman/` 和配置文件
- `bestman` — 仪表盘：20×9 像素地图 + 进度条 + 今日任务
- `bestman done` — 完成今日任务，推进一格，生成日志
- `bestman log` — 查看最近航海日志

**基础设施**
- Click CLI + Rich 终端渲染
- SQLite WAL 持久化（`days` + `voyage_logs` 表）
- YAML 配置（`~/.bestman/config.yaml`），deep merge 默认值
- 15 条硬编码航海日志模板，按 day 确定性随机轮换
- 7 个航行阶段 + 7 个里程碑（每 25 天），从 config 读取

**技术栈**
- Python 3.12 + uv
- Click 8.x（CLI 框架）
- Rich 13.x（终端渲染）
- PyYAML（配置）
- 60 个测试

### 路线演变

| 路线 | 描述 | 结果 |
|------|------|------|
| 路线 A | 独立 Python CLI | ✅ 最终采用 |
| 路线 B | Claude Code skill 做引擎 | ❌ 路线错误，Claude Code 应是调用方不是引擎 |
| 路线 C | CLI + Claude Code 薄壳 | ✅ 当前架构 |
