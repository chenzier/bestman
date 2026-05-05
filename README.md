# bestman

把健身变成一个航海游戏。

一个 Python CLI 工具。每天完成训练任务 → 掷骰子在大海地图上前进 → AI 导航员帮你写航海日志。用游戏机制对抗拖延症。

## 核心玩法

```
每天打卡训练  →  掷骰子推进 1-6 格  →  在像素地图上前进  →  航行日志 + 金币 + 宝藏
```

地图上有迷雾、阶段、里程碑和随机事件。连续打卡有连击奖励，可以用「跳过令牌」休息一天不打断连击。

## 安装

需要 Python 3.12+。

```bash
git clone https://github.com/chenzier/bestman.git
cd bestman
uv sync
```

或者用 pip：

```bash
pip install -e .
```

## 快速上手

```bash
bestman init         # 初始化航行
bestman done         # 完成今日训练，掷骰子前进
bestman              # 查看仪表盘（地图 + 进度 + 今日任务）
bestman log          # 查看航海日志
```

## 命令速览

| 命令 | 说明 |
|------|------|
| `bestman` | 查看仪表盘（像素地图 + 今日任务 + 进度） |
| `bestman init` | 初始化航行数据 |
| `bestman done` | 完成今日训练，掷骰推进 |
| `bestman done --mode interactive` | 互动掷骰模式（按键停止，更有参与感） |
| `bestman done -e N` | 掷骰结果 + 手动额外 N 格 |
| `bestman done -m "内容"` | 手动写日志（跳过 AI 生成） |
| `bestman skip` | 使用跳过令牌休息一天，不中断连击 |
| `bestman log` | 查看航海日志 |
| `bestman talk` | 与 AI 导航员对话（可调整训练计划） |
| `bestman plan create` | 交互式制定健身计划（减肥 / 增肌 / 自定义） |
| `bestman plan show` | 查看当前计划 |
| `bestman plan edit` | 用编辑器修改计划 |
| `bestman weigh 70.5` | 记录体重 |
| `bestman progress` | 查看体重趋势和预计达标日期 |
| `bestman review` | 本周回顾（打卡率 + 航行距离 + AI 总结） |
| `bestman map` | 查看完整航行地图和阶段进度 |
| `bestman vessel list` | 查看可切换的载具 |
| `bestman vessel set <名称>` | 切换载具（不同外观） |
| `bestman config dice-mode` | 查看 / 切换骰子模式 |
| `bestman reset` | 重置所有数据 |

## 配置

### LLM（AI 导航员）

在 `~/.bestman/.env` 中配置 OpenAI 兼容接口：

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com   # 或其他兼容 API
LLM_MODEL=deepseek-v4-pro
```

不配置 LLM 也能正常使用——`done` 会用模板生成日志，`plan create` / `talk` 等功能需要 LLM。

### 主题

内置两套主题：

- `naval`（默认）—— 航海主题，船、海域、金币、宝藏
- `cultivation` —— 修仙主题，飞剑、洞府、灵石

修改 `~/.bestman/config.yaml` 中 `voyage.theme` 字段即可切换。

### 自定义配置

初始化后 `~/.bestman/config.yaml` 包含完整默认配置：地图大小、航程天数、阶段划分、里程碑、骰子权重、金币规则、随机事件、宝藏等。直接编辑即可。

## 原理

```
bestman/           ← CLI 源码
~/.bestman/        ← 运行时数据（config.yaml、plan.yaml、SQLite 数据库）
```

地图用 Kitty 终端协议渲染为像素 PNG，支持 ASCII 降级。245 个测试覆盖核心逻辑。

## 进阶文档

- [CHANGELOG.md](./CHANGELOG.md) — 版本变更记录
- [docs/ROADMAP.md](./docs/ROADMAP.md) — 路线图
- [docs/superpowers/](./docs/superpowers/) — 设计文档和实现计划
