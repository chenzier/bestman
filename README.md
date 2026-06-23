# bestman

把健身打卡做成一个宠物船陪伴系统。

当前主入口是 **Rust 版 `bestman`**。Python 版仍保留在仓库中，但只作为 legacy/prototype 参考，不再作为新功能主线。

## 当前定位

bestman 的核心不再是“航海地图游戏”，而是“宠物船陪伴 + 健身打卡”：

```text
每天训练打卡 -> 宠物船状态变化 -> 航线进度推进 -> 航海日志与奖励
```

地图只表达长期进度；宠物船是主要体验。

## 安装与运行

需要 Rust toolchain。

```bash
git clone https://github.com/chenzier/bestman.git
cd bestman
cargo install --path .
bestman --home /tmp/bestman-demo init
bestman --home /tmp/bestman-demo tui
```

实时 TUI：

```bash
bestman --home /tmp/bestman-demo tui --live
```

如果终端支持 Kitty/Ghostty/WezTerm 图片协议，可以启用图片船：

```bash
bestman --home /tmp/bestman-demo tui --live --images
```

退出实时 TUI：

```text
q / Esc / Ctrl-C
```

## 常用命令

| 命令 | 说明 |
|------|------|
| `bestman --home <dir> init` | 初始化配置、事件日志和默认船 |
| `bestman --home <dir> status` | 查看当前状态 |
| `bestman --home <dir> status --json` | 输出 JSON 状态 |
| `bestman --home <dir> reset --yes` | 清空该 home 下的本地数据 |
| `bestman --home <dir> done --level full --dice 3` | 完成今日训练，推进航程 |
| `bestman --home <dir> done --mock-llm` | 使用 mock LLM 生成航海日志 |
| `bestman --home <dir> done --llm` | 尝试真实 LLM 航海日志，失败时保留模板日志 |
| `bestman --home <dir> skip` | 记录休息/跳过 |
| `bestman --home <dir> log` | 查看最新航海日志 |
| `bestman --home <dir> recap` | 生成本地长期回顾并写入日志 |
| `bestman --home <dir> recap --llm` | 尝试 LLM 长期回顾，失败时本地 fallback |
| `bestman --home <dir> plan create --goal <goal> --tasks "A,B"` | 创建本地轻量训练计划 |
| `bestman --home <dir> plan show` | 查看当前计划和今日任务 |
| `bestman --home <dir> plan set-today "<task>"` | 手动调整今日任务 |
| `bestman --home <dir> vessel list` | 查看可用船只 |
| `bestman --home <dir> vessel set <id>` | 切换当前船只 |
| `bestman --home <dir> shop list` | 查看商店船只、价格、稀有度和拥有状态 |
| `bestman --home <dir> shop buy <item_id>` | 购买已注册 catalog 的船只 |
| `bestman --home <dir> tui` | 打开静态宠物船面板 |
| `bestman --home <dir> tui --live --images` | 打开实时宠物船 TUI |
| `bestman preview --animation sailing --output /tmp/ship.png` | 导出船只预览 PNG |
| `bestman --home <dir> dashboard-image --output /tmp/dashboard.png` | 导出 dashboard PNG |
| `bestman animation-frames --animation sailing --output-dir /tmp/frames` | 导出船只动画帧 |
| `bestman --home <dir> dashboard-frames --output-dir /tmp/dashboard-frames` | 导出 dashboard 动画帧 |

实时 TUI 按键：

| 按键 | 说明 |
|------|------|
| `L` | light 打卡 |
| `N` | normal 打卡 |
| `F` | full 打卡 |
| `S` | rest/skip |
| `Q` / `Esc` / `Ctrl-C` | 退出 |

## 数据目录

`--home <dir>` 指定 bestman 的运行时数据目录。目录结构：

```text
<home>/
  config.toml       # 配置
  events.jsonl      # append-only 事件日志
  bestman.db        # SQLite 投影，可从 events.jsonl 重建
  cache/            # 船只帧缓存
  vessels/          # 用户自定义船只
```

不传 `--home` 时会使用系统应用数据目录。开发时建议显式传入临时目录，避免污染真实数据：

```bash
bestman --home /tmp/bestman-demo status
```

## LLM 配置

真实 LLM 叙事是可选增强。它只写航海日志，不改金币、位置、心情、信任或奖励。

```toml
[llm]
enabled = true
provider = "openai_compatible"
base_url = "https://api.openai.com/v1"
api_key_env = "OPENAI_API_KEY"
model = "gpt-4o-mini"
prompt_version = "bestman-v2-narrative"
```

运行时设置对应环境变量：

```bash
export OPENAI_API_KEY=...
bestman --home /tmp/bestman-demo done --llm
```

如果 LLM 不可用，打卡仍会成功，并保留本地模板日志。

## 船只资产

内置默认船：

```text
assets/catalog.json
assets/vessels/starter_sloop/
  vessel.json
  spritesheet.png
```

`vessel.json` 只描述渲染资产：船只 ID、显示名、帧尺寸和动画序列。商店、价格、稀有度和解锁条件由 `assets/catalog.json` 管理。

用户自定义船只属于 experimental，必须在 `<home>/catalog.json` 注册：

```text
<home>/catalog.json
<home>/vessels/<vessel-id>/vessel.json
<home>/vessels/<vessel-id>/spritesheet.png
```

当前会校验 manifest，并拒绝 spritesheet 路径逃逸。v1.2 开始，未注册 catalog 的船不会进入商店、列表或装备流程。

## 架构

Rust 版采用：

```text
src/events.rs       # append-only 事件源
src/projection.rs   # SQLite 当前状态投影
src/rules.rs        # 打卡、休息、购买、换船规则
src/vessels/        # 船只 catalog / manifest / frame rendering
src/tui.rs          # 宠物船 TUI
src/dashboard.rs    # dashboard PNG 导出
src/terminal_image.rs # Kitty/Sixel 探测与 Kitty 图片协议
```

关键边界：

- 规则系统拥有状态变更权。
- LLM 只生成叙事，不直接改金币、心情、位置等状态。
- SQLite 是 projection，不是事实来源。
- `events.jsonl` 是事实来源。
- 船只表现由 spritesheet + manifest 驱动。

## Python Legacy

`bestman/` 目录里的 Python 实现是早期 prototype，包含旧 CLI、地图、主题、计划和 LLM 探索代码。

现阶段约定：

- 新功能优先进入 Rust 版。
- Python 版不再作为用户主入口。
- Python 版可作为需求/玩法参考，但不要和 Rust 版并行扩新架构。
- 旧 Python 测试仍可保留，用于理解历史行为。

如果确实需要运行旧 Python prototype：

```bash
uv sync
uv run bestman --help
```

## 验证

Rust 主线门禁：

```bash
cargo fmt --check
cargo test
```

当前测试覆盖：

- 事件重放与 SQLite 投影
- 打卡/休息/购买/换船规则
- mock LLM 日志替换
- vessel manifest 校验和路径逃逸拒绝
- 船只预览、动画帧、dashboard PNG 导出
- Kitty 图片协议编码
- TUI 静态/实时/scripted 输入和退出

## 后续重点

1. v3.x 叙事扩展：里程碑史诗、可选船员/角色。
2. `bestman config show` 和安全的高频配置命令。
3. 发布包和升级说明。
