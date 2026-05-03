# bestman 技术路线

> 最后更新：2026-05-03
> 当前版本：v1.0.0

---

## 架构概览

```
cli.py ──→ voyage.py ──┬──→ config.py (YAML 配置)
                        ├──→ state.py  (SQLite 持久化)
                        ├──→ map_engine.py (地图渲染)
                        ├──→ llm.py    (AI 日志 + 教练)
                        └──→ events.py (随机事件)
```

三层：展示层（cli.py）→ 逻辑层（voyage.py）→ 数据层（state.py + config.py）+ 渲染层（map_engine.py）+ AI 层（llm.py + events.py）

---

## v1.0.0 — 全功能航海 ✅ 已完成

| 功能 | 命令 |
|------|------|
| 初始化航行 | `bestman init` |
| 仪表盘 | `bestman` |
| 完成打卡（掷骰子 1-3 格） | `bestman done [-e N] [-f] [-d DATE]` |
| 跳过（休整令牌） | `bestman skip` |
| AI 教练对话 | `bestman talk [-m MSG]` |
| 查看航海日志 | `bestman log [-n N]` |
| 查看航行计划 | `bestman plan` |
| 重置数据 | `bestman reset [-y]` |

**技术栈：** Python 3.12, Click, Rich, SQLite WAL, OpenAI SDK, uv
**测试：** 137 tests

---

## v1.1 — 打卡后互动

**目标：** 解决"done 完就没事做"的问题。打卡后增加可做的事情，让 app 从"每日打卡机"变成"每日航海生活"。

### 探索海域 (`bestman look`)

查看当前所在位置的世界细节。LLM 生成一段海域描述。

```bash
$ bestman look
你正在季风带中部海域。西南风 15 节，浪高 1.5 米。
左舷远处有飞鱼群跃出水面，右舷 3 海里处有一座无名礁岛，
岛上有海鸟盘旋。前方 8 格就是贸易港了——

导航员说：这片海域的飞鱼是幸运的象征，许多老水手在这里捡到过漂流瓶。
```

同一位置多次 look 产生不同细节（LLM 随机性），不限次数。无 LLM 时用模板。

### 教练主动提问 (`bestman talk` 升级）

done 后教练不只是等用户开口，而是主动抛一个问题：

```
$ bestman done
✓ 完成！
"海风推着帆..."

导航员看着你说：今天训练中最难的是什么？
>
```

用户回答后教练回应。让对话有"被关心"的感觉。

### 航行统计 (`bestman stats`)

```bash
$ bestman stats
══════════ 航行统计 ═══════════
总航行：12 天
总计里程：19 海里
平均速度：1.58 海里/天
最长连击：7 天（获得 1 枚令牌）
里程碑达成：1/7（穿越迷雾之海）
累计天数：10/175
预计到达：2026-10-18（提前 7 天！）
```

无需 LLM，纯 SQL 聚合。

### 手写航海日志 (`bestman journal`)

```bash
$ bestman journal "今天加班到 10 点但还是做了静蹲。值得。"
✓ 已记入航海日志
```

存入 voyage_logs，和 AI 日志同表，标注 `event_type: journal`。`bestman log` 混合展示。

### 明日天气 (`bestman tomorrow`)

```bash
$ bestman tomorrow
明天进入季风带。季风带以强顺风闻名——历史上 60% 的水手在这里
一天航行 2-3 格。但偶尔也有逆风天，只航行 1 格。
导航员建议：明天精力好可以挑战 -e 2，季风会帮你。
```

LLM 生成，带阶段信息。无 LLM 时用硬编码提示。

### 影响范围

| 文件 | 改动 |
|------|------|
| `bestman/cli.py` | 加 `look`、`stats`、`journal`、`tomorrow` 命令；`done` 加教练提问 |
| `bestman/voyage.py` | 加 `look()`、`tomorrow()`、`journal()` 方法 |
| `bestman/llm.py` | 加 `look_prompt`、`tomorrow_prompt` |
| `bestman/state.py` | `get_logs` 加 `event_type` 过滤；加 `get_stats()` 聚合查询 |
| `tests/` | 对应测试新增 |

---

## v1.2 — 地图修缮 + 多航线

**目标：** 修掉 `░▓` 乱码视觉问题；航线完成后可开启下一条。

| 功能 | 说明 |
|------|------|
| 统一迷雾 | `░▓` 变统一 `▒`，去掉随机扰动 |
| `bestman new` | 第一条航线完成后，开启新航线（新目标、新日期） |
| 航线存档 | 已完成航线保留在 `~/.bestman/archives/`，可回看 |

---

## v2.0 — 2D 多地图 + 宝藏 + 金币

**目标：** 地图从一维横条变为真正的 2D 世界；引入经济系统。

### 2D 多地图系统

每个阶段 = 一张独立地图（如 30×10 网格），合起来构成世界。

```
已完成的启航地图（缩略图）  当前季风带地图（全尺寸）       锁定的迷雾之海（预览）
┌────────────┐           ┌──────────────────────┐         ┌────────────┐
│ ✓ 启航     │     →     │ ≈≈≈≈⚓∘∘∘∘∘💎▒▒▒▒▒  │    →    │ 🔒 信风带  │
│ 25/25      │           │ ≈≈≈≈≈≈≈∘∘∘∘∘▒▒▒▒▒  │         │ 0/25       │
└────────────┘           │ ≈≈≈≈≈≈≈≈✦∘∘∘∘∘∘▒▒▒  │         └────────────┘
                         └──────────────────────┘
```

**MapEngine 架构（预留给创意工坊的接口）：**

```python
class MapEngine:
    def __init__(self, map_def: dict):
        """map_def 可以来自 config.yaml 内联定义，也可以来自外部文件。

        创意工坊的地图文件就是同样的 dict 结构，从 YAML/JSON 文件加载。
        """
        self.name = map_def["name"]
        self.width = map_def["width"]
        self.height = map_def["height"]
        self.tiles = map_def["terrain"]       # 2D array
        self.route = map_def["route"]          # [(x,y), ...]
        self.treasures = map_def.get("treasures", [])
        self.entry = map_def["entry_point"]
        self.exit = map_def["exit_point"]

    @staticmethod
    def from_file(path: str) -> "MapEngine":
        """从文件加载地图定义（工坊接口入口）。"""
        with open(path) as f:
            map_def = yaml.safe_load(f)
        return MapEngine(map_def)

    def render(self, tiles_revealed) -> str:
        """渲染当前地图为 Rich markup 字符串。"""
        ...

class WorldMap:
    """管理多张地图的切换。"""
    def __init__(self, maps: list[dict]):
        self.maps = [MapEngine(m) for m in maps]
        self.current_idx = 0

    def current(self) -> MapEngine:
        return self.maps[self.current_idx]

    def advance(self):
        """切换到下一张地图。"""
        self.current_idx += 1
```

### 宝藏系统

| 类型 | 显示 | 发现方式 |
|------|------|---------|
| 显式宝藏 | 地图上 `💎` 标记 | 航行到该位置时触发 |
| 隐式宝藏 | 不可见 | 每次 done 8% 概率触发 |

### 金币系统

| 行为 | 金币 |
|------|------|
| 每日打卡 | +10 |
| 掷骰 3 格 | +5 |
| 超额 `-e N` | +5 × N |
| 连击 7 天 | +25 |
| 里程碑到达 | +100 |
| 显式宝藏 | 30-100 |
| 隐式宝藏 | 10-80 |

### CLI 新增

```bash
bestman coins           # 查看金币余额和历史
bestman map             # 查看所有地图概览
bestman map current     # 查看当前地图
```

---

## v2.1 — 商店

**目标：** 金币可消费，解锁主题/皮肤/道具。

```bash
bestman shop                 # 浏览商品
bestman shop buy ID          # 购买
bestman shop inventory       # 查看已拥有
```

| 商品类型 | 价格 | 示例 |
|---------|------|------|
| 主题 | 500 金币 | 修仙主题、废土主题 |
| 船皮肤 | 300 金币 | 金色帆船、幽灵船、龙头船 |
| 道具 | 100 金币 | 双倍骰子（下次 done 掷骰×2）、顺风保证（下次 done 必 3 格） |

---

## v2.2 — 创意工坊

**目标：** 用户可创建/分享自定义地图。

```
~/.bestman/
├── maps/
│   ├── custom_dragon_island.yaml   ← 用户自制地图
│   └── community_pirate_cove.yaml  ← 从社区下载的
└── config.yaml                      ← 主配置引用自定义地图
```

**地图文件格式（标准接口）：**

```yaml
# ~/.bestman/maps/dragon_island.yaml
name: "龙之岛"
version: 1
width: 30
height: 10
tiles:                          # 2D 地貌数组
  - [ocean, ocean, reef, reef, volcano, volcano, ...]
  - ...
route: [[0,5], [1,5], [2,4], ...]   # 航线坐标序列
treasures:
  explicit:
    - {name: "龙蛋", pos: 15, coins: 200, message: "..."}
  implicit:
    - {name: "火山灰金币", coins: 30, message: "..."}
    - {name: "海怪鳞片", coins: 50, message: "..."}
entry_point: [0, 5]
exit_point: [29, 3]
theme: "naval"
description: "穿越龙之岛的火山海域"
author: "水手小王"
difficulty: 3
```

**加载命令：**

```bash
bestman map install ~/Downloads/dragon_island.yaml   # 安装自定义地图
bestman map list                                       # 列出可用地图
bestman map select dragon_island                       # 选择地图作为下一条航线
bestman map export dragon_island                        # 导出地图文件（分享用）
```

**MapEngine.from_file()** 就是工坊加载的入口。所有地图都用同一个接口，无论内置还是自定义。

---

## v2.3 — 饮食管理

**目标：** 减肥 = 运动 + 饮食。只管理运动是不够的，需要饮食记录和反馈。

### 设计原则

- **不追踪卡路里**（追踪卡路里是高压行为，容易触发放弃）
- 改为**意识记录**：记下吃了什么，AI 导航员温和反馈
- 和运动系统解耦——饮食不影响航行进度，是独立维度

### 命令

```bash
bestman eat "午餐：鸡胸肉沙拉 + 糙米饭"
bestman eat "下午：没忍住吃了一包薯片"
bestman diet              # 查看今日饮食记录
bestman diet -w           # 查看本周饮食概览
```

### AI 反馈

`bestman eat` 之后，LLM 生成一段简短反馈（2-3 句）：

```
$ bestman eat "午餐：鸡胸肉沙拉 + 糙米饭"
🥗 已记录
导航员：鸡胸肉和糙米饭——蛋白质和慢碳的组合。水手们在长途航行中
最珍视这样的补给，能撑到黄昏不饿。
```

```
$ bestman eat "下午：没忍住吃了一包薯片"
🥗 已记录
导航员：一包薯片是一阵突风，不会让船偏离航线。下次饿的时候，
厨房里有提前备好的坚果——导航员的建议。
```

关键：不审判、不羞辱、不焦虑。吃了薯片就吃了，船还在航线上。

### 每日饮食简报

`bestman` dashboard 底部加一行饮食状态：

```
🍽 今日饮食：3 条记录（鸡胸肉沙拉、糙米饭、薯片）
导航员：蛋白质够了，下午的零食选择可以再想想。
```

`bestman diet -w` 显示过去 7 天的饮食模式，AI 总结趋势（不评分）。

### 影响范围

| 文件 | 改动 |
|------|------|
| `bestman/state.py` | 加 `meals` 表（date, text, created_at） |
| `bestman/cli.py` | 加 `eat`、`diet` 命令；dashboard 加饮食行 |
| `bestman/llm.py` | 加 `meal_feedback()` 方法 |
| `bestman/voyage.py` | 加 `record_meal()`、`get_meals()` |

---

## v3.0 — 外部主题市场 + 社区

**目标：** 主题和地图的分享生态。

- 主题文件格式标准化（和地图类似）
- 社区地图排行榜
- 导入/导出航线数据

---

## 总时间线

```
v1.0.0 ──→ v1.1 ──→ v1.2 ──→ v2.0 ──→ v2.1 ──→ v2.2 ──→ v2.3 ──→ v3.0
 ✅       打卡互动   地图修缮   2D多地图   商店     创意工坊   饮食管理   社区
          look      迷雾统一   宝藏+金币
          stats     多航线
          journal
          tomorrow
```

当前 v1.0.0，下一步 v1.1（打卡后互动）。
