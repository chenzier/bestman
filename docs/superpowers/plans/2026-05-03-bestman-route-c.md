# bestman Route C — 实现计划

> **架构决策：** CLI 是产品本体。Claude Code 是调用窗口（薄壳转发命令，不做逻辑）。

**Goal:** 构建 bestman Python CLI demo——最小可用原型，跑通"查看地图 → 打卡 → 推进"核心循环。

**Architecture:** 三层 CLI：`bestman` (click group) → `Voyage` (游戏逻辑) → `BestmanState` (SQLite) + `MapEngine` (Rich 渲染)。数据在 `~/.bestman/`。

**Tech Stack:** Python 3.12, click, rich, SQLite WAL, pyyaml, python-dotenv, uv

---

## Demo 范围

### 包含

| 功能 | 命令 |
|------|------|
| 初始化航行 | `bestman init` |
| 查看仪表盘（地图+进度+任务）| `bestman` |
| 完成今日任务，推进一格 | `bestman done` |
| 查看航海日志 | `bestman log` |

### 不包含（后续版本）

- LLM 集成（demo 用硬编码的航海日志模板）
- `bestman skip` / 休整令牌
- `bestman done -e N` 超额推进
- `bestman talk` AI 教练对话
- 主题系统（只硬编码 naval）
- Claude Code wrapper
- 连击系统（demo 暂不追踪连续天数）

---

## Demo 完成后用户看到的

```
$ bestman init
⚓ bestman 号已就绪
航线：2026-05-03 → 2026-10-25
航程：175 天
每日必定任务：死虫式 3×10 + 静蹲 2×30秒
数据目录：~/.bestman/

$ bestman
══════════════ bestman — 航向新大陆 ═══════════════

航向新大陆
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
...

DAY 0/175 · 启航 · 剩余 175 天
████████░░░░░░░░░░░░░░░░░░░░ 0/175
🔥 连击 0 天 · 🛡️ 令牌 0 · 📍 0/175

今日任务：死虫式 3×10 + 静蹲 2×30秒

$ bestman done
✓ 完成！推进了 1 格

Day 1 · 启航
晨光洒在甲板上，bestman 号缓缓驶出港口。水手们精神抖擞，风帆鼓满西风。
前方是 174 天的未知海域——但今天，我们只需要航行这一格。

（地图更新...）

$ bestman log
2026-05-03: Day 1 · 晨光洒在甲板上...
```

---

## 文件结构

```
bestman/
├── pyproject.toml
├── .env.example
├── bestman/
│   ├── __init__.py
│   ├── config.py          # YAML 配置加载
│   ├── state.py           # SQLite 状态管理
│   ├── map_engine.py      # 像素地图渲染
│   ├── voyage.py          # 游戏逻辑（连击、里程碑、日志模板）
│   └── cli.py             # Click CLI 入口
├── tests/
│   ├── test_state.py
│   ├── test_config.py
│   ├── test_map_engine.py
│   └── test_voyage.py
├── skills/
│   └── bestman/
│       └── SKILL.md       # Claude Code 薄壳（后续版本，demo 不激活）
├── docs/
│   └── ...
└── README.md
```

---

## Worktree 拆分

```
Worktree 1: 脚手架 + Config + State（基础层，零依赖）
    ↓
Worktree 2: Map Engine（依赖 Worktree 1 的接口定义）
    ↓
Worktree 3: Voyage + CLI（依赖 Worktree 1+2，连线成产品）
```

每个 worktree 独立可测。最后 merge 后做一次集成测试。

---

### Worktree 1: 基础层（Config + State）

**前置：** 无
**产出：** `bestman/config.py`, `bestman/state.py`, `pyproject.toml`, `bestman/__init__.py`, `.env.example`, 以及对应测试

#### Task 1.1: 项目脚手架

```bash
cd /Users/admin/project/test/bestman
uv init --name bestman --python 3.12 --no-package  # 如果 pyproject.toml 不存在
uv add click rich pyyaml python-dotenv
```

创建 `pyproject.toml`，入口点：
```toml
[project.scripts]
bestman = "bestman.cli:main"
```

#### Task 1.2: Config 模块

`bestman/config.py` — 负责：
- `BESTMAN_HOME = Path.home() / ".bestman"`
- `ensure_home()` — 创建目录，如果 config.yaml 不存在则写入默认值
- `load_config()` — 读取 YAML，deep merge 默认值
- `DEFAULT_CONFIG` — 包含 voyage days、stages、milestones、profile、default_daily_task

**测试：** `test_config.py`
- 测试 `ensure_home` 创建目录和文件
- 测试 `load_config` 返回带默认值的字典
- 测试 `BESTMAN_HOME` 路径正确

#### Task 1.3: State 模块

`bestman/state.py` — SQLite，WAL 模式。两张表：
- `days (date TEXT PK, completed INT, extra INT, task_done TEXT, used_skip INT, created_at TEXT)`
- `voyage_logs (id INTEGER PK, date TEXT, text TEXT, created_at TEXT)`

方法：
- `record_day(date, completed, extra, task_done)` → void
- `today_recorded(date=None)` → bool
- `get_tiles_revealed()` → int（completed days + sum(extra)）
- `get_completed_days()` → int
- `save_log(date, text)` → void
- `get_logs(limit)` → list[dict]

**Demo 不包含：** skip_tokens 表、streak 计算、milestones 表（这些留到后续 worktree）

**测试：** `test_state.py`
- 测试建表
- 测试 record_day 和查询
- 测试 tiles_revealed = completed + extra
- 测试 today_recorded 判定
- 测试 save_log / get_logs

---

### Worktree 2: Map Engine

**前置：** Worktree 1（需要知道 total_days、milestones 的定义，但不需要 state 模块）
**产出：** `bestman/map_engine.py`, `tests/test_map_engine.py`

#### Task 2.1: Map Engine

`bestman/map_engine.py` — 纯函数式，不依赖 SQLite。输入数据，输出 Rich markup 字符串。

```python
class MapEngine:
    def __init__(self, total_days=175, milestones=None):
        self.total_days = total_days
        self.milestones = milestones or {}
        self.cols = 20
        self.rows = (total_days + self.cols - 1) // self.cols

    def render(self, tiles_revealed=0):
        """返回 Rich markup 字符串。
        - 未揭示格：▒ (dim blue)
        - 已揭示格：~ (cyan)
        - 当前船位（最后一格）：⚓ (bold yellow)
        - 里程碑格：✦ (bold magenta)"""
```

地图 20 列宽。175 天 = 9 行（最后一行不满）。

地图下方的信息栏由 CLI 负责显示（map_engine 只管地图本身）。

**内置航海日志模板（硬编码，demo 不用 LLM）：**

```python
VOYAGE_LOG_TEMPLATES = [
    "晨光洒在甲板上，bestman 号缓缓驶出港口。风帆鼓满西风，前方是未知的海洋。但今天，我们只需要航行这一格。",
    "海面平静如镜。瞭望手在主桅上打盹，舵手哼着古老的船歌。平静的一天也是好的一天。",
    "西南风转强，船身微微倾斜。水手们收紧帆索，甲板上响起整齐的号子声。乘风破浪就是这种感觉。",
    # ... 总共准备 10-15 条，随机轮换
]

def get_log_entry(day, stage):
    import random
    random.seed(day)  # 同一天永远返回同一条日志
    return random.choice(VOYAGE_LOG_TEMPLATES)
```

**测试：** `test_map_engine.py`
- 测试初始地图全是 `▒`
- 测试推进 N 格后有 N 个 `~` + 1 个 `⚓`
- 测试里程碑位置显示 `✦`
- 测试 175 格全部揭示后不再崩溃
- 测试 `get_log_entry(1)` 确定性返回

---

### Worktree 3: Voyage + CLI（连线）

**前置：** Worktree 1 + 2
**产出：** `bestman/voyage.py`, `bestman/cli.py`, `tests/test_voyage.py`, `tests/test_cli.py`

#### Task 3.1: Voyage 游戏逻辑

`bestman/voyage.py` — 连接 state + map_engine + config：

```python
class Voyage:
    def __init__(self):
        self.config = load_config()
        self.state = BestmanState()
        self.map_engine = MapEngine(
            total_days=self.config["voyage"]["total_days"],
            milestones=self.config.get("milestones", {}),
        )

    def get_status(self):
        return {
            "tiles_revealed": self.state.get_tiles_revealed(),
            "current_day": self.state.get_tiles_revealed() + 1,
            "total_days": self.config["voyage"]["total_days"],
            ...
        }

    def get_daily_task(self):
        return self.config["voyage"]["default_daily_task"]

    def render(self):
        return self.map_engine.render(self.state.get_tiles_revealed())

    def complete(self, date=None):
        # 1. 检查今日是否已记录
        # 2. record_day
        # 3. 生成日志（模板）
        # 4. save_log
        # 5. 检查里程碑
        # 6. 返回结果

    def get_logs(self, limit=10):
        return self.state.get_logs(limit)
```

**测试：** `test_voyage.py`
- 测试 init 后 tiles_revealed = 0
- 测试 complete 后 tiles_revealed = 1
- 测试同一天重复 complete 被拒绝
- 测试 complete 返回的信息包含 log 文本
- 测试里程到达时返回 milestone 标记

#### Task 3.2: CLI

`bestman/cli.py` — click group，四个命令：

```python
@click.group(invoke_without_command=True)
def main():
    """bestman — 航向新大陆"""

@main.command()
def init():
    """初始化"""

@main.command()
def dashboard():  # 默认命令，bestman 不带参数时触发
    """仪表盘"""

@main.command()
def done():
    """完成今日任务"""

@main.command()
@click.option("-n", "--count", default=10)
def log(count):
    """查看日志"""
```

渲染顺序（dashboard）：
```
规则线 "bestman — 航向新大陆"
空行
地图（map_engine.render()）
空行
今日任务
[如果今日已完成：绿色提示]
最近日志（最后 3 条，截断到 100 字符）
命令提示
```

---

## 后续版本规划

| 版本 | 内容 | 大致开发量 |
|------|------|-----------|
| **Demo** | init / dashboard / done / log，硬编码日志，SQLite，像素地图 | 当前计划 |
| **v0.2** | LLM 集成（voyage log 生成），`.env` 加载 | 1 worktree |
| **v0.3** | `bestman talk` 教练对话 | 1 worktree |
| **v0.4** | skip 系统（休整令牌），`done -e N` 超额，连击 | 1 worktree |
| **v0.5** | 主题系统抽象（naval / cultivation） | 1 worktree |
| **v0.6** | Claude Code 薄壳 skill (`/bestman`) | 1 worktree |
| **v1.0** | 里程碑特殊叙事，真实节日锚点，6 阶段航线联动 | 集成 |

---

## 执行策略

### 单 worker（顺序）

```
Worktree 1 → 测试通过 → commit
Worktree 2 → 测试通过 → commit
Worktree 3 → 测试通过 → commit
集成测试 → commit
```

### 多 worker（并行）

Worktree 1 和 Worktree 2 可以并行（2 只依赖 1 的接口定义，不依赖其实现）。写完 1 的接口签名后即可并行启动 2。

```
Worktree 1 ──┬── Worktree 3（连线）
Worktree 2 ──┘
```

---

## 当前状态

- [ ] Worktree 1: Config + State
- [ ] Worktree 2: Map Engine
- [ ] Worktree 3: Voyage + CLI
- [ ] 集成测试
