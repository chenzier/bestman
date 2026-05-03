# Changelog

All notable changes to bestman will be documented in this file.

---

## v1.2.0 (2026-05-04) — 计划系统 + 地图增强

### 新增

**计划系统**（回归产品本体）
- `bestman plan create` — 交互式制定健身计划：选择目标（减肥/增肌/习惯/自定义）、输入体重、周期、运动基础、偏好，LLM 生成分阶段计划保存到 `~/.bestman/plan.yaml`
- `bestman plan show` — 查看当前计划（目标、阶段、里程碑、每日任务）
- `bestman plan edit` — 用 `$EDITOR` 直接编辑 plan.yaml

**回顾 + 身体数据**
- `bestman review` — 周回顾：聚合打卡率、航行距离、金币 + LLM 总结
- `bestman weigh 128.5` — 记录体重，自动计算 delta、距目标距离
- `bestman progress` — 体重趋势图（最近 4 次记录），周均变化 + 预计达标日期

**自适应计划**
- `bestman talk` 支持修改计划——教练对话中可以说"膝盖不舒服"，教练自动临时替换动作（如静蹲 → 坐姿抬腿），N 天后自动恢复

**地图增强**
- 今日航线高亮动画——done 后今天走过的 tile 金色闪烁
- 船体摇摆动画——抵达新 tile 后船身左右摇摆再稳定（1.5 秒）
- 光标重绘代替 `console.clear()`，无闪屏

**手动日志**
- `bestman done -m "今天下雨，室内俯卧撑 50×3"` — 跳过 LLM，手写日志文本

### 改动

- `bestman plan` 命令改名为 `bestman map`（释放 plan 命名空间）
- 掷骰互动模式优化：数字显示 + 稀有结果加权
- 配置：`config.yaml` 加 `today_trail.sway` 动画配置段
- 245 tests（+15）

---

## v1.1.0 (2026-05-04) — 2D 世界 + 掷骰 + 宝藏

### 新增

**2D 世界地图**
- 50×14 网格渲染，航线沿坐标蜿蜒前行
- 不同海域不同地貌：`~` 启航、`▒` 迷雾之海、`∿` 贸易航线、`/` 信风带、`—` 赤道无风带
- 迷雾只覆盖未探索区域（船周围半径外），走过航线永久可见
- 前方可见 10 格航线 `∘`，再远隐于迷雾
- `bestman plan` 查看全阶段航行计划

**掷骰子系统**
- `bestman done` 掷骰 1-3 格（60%/30%/10% 权重），不再固定 +1
- 互动掷骰 `--mode interactive`：数字滚动动画，按键停止，参与感更强
- `-e N` 额外推进叠加在骰子结果上

**宝藏 + 金币系统**
- 显式宝藏：地图上 `💎` 标记，航行到该格时触发
- 隐式宝藏：每次 done 8% 概率触发，有意外惊喜
- 金币产出：每日打卡 +10、骰子 3 格 +5、超额 +5×N、连击 7 天 +25、里程碑 +100、宝藏 20-100
- `bestman coins` 查看金币余额和获取历史

**主题系统**
- `bestman/themes/` 目录：`naval`（航海）、`cultivation`（修仙）两个预设
- config `theme` 字段切换，主题控制人物名、地貌字符、叙事语气
- `bestman themes` 查看可用主题

**航海员系统（架构预留）**
- `bestman talk` 支持多 persona，为船员系统预留接口

### 变更

- 地图从一维横条变为 2D 世界（`MapEngine` 重写）
- `done` 命令加 `-f`（强制重新打卡）和 `-d DATE`（指定日期）测试参数
- `bestman reset -y` 一键重置数据
- 216 tests（+79）

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
