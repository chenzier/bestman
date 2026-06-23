# P1-P5 执行方案

> 最后更新：2026-06-23

本文档把当前高层路线拆成可执行、可验收、可提交的五个阶段。每个阶段都必须满足：实现完成、自动化验证通过、文档同步、独立 commit，并推送到远端。

## P1 TUI 可用主界面

目标：

- `bestman tui` 可作为日常主入口，首屏直接显示当前宠物船、今日任务、路线进度和核心状态。
- `bestman tui --live` 可退出、可脚本化验证，并支持 Today / Plan / Shop / Fleet / Log 标签页。
- 图片模式是增强能力，失败时必须回退文本界面。

范围：

- 静态 TUI 首屏渲染。
- live TUI 标签页、退出键、脚本输入。
- 今日任务、金币、心情、信任、streak、路线进度展示。
- dashboard PNG / frame cache 不破坏 TUI 使用。

不做：

- 不做地图主玩法。
- 不做全屏复杂配置编辑器。
- 不把收集进度抢到首屏主视觉。

涉及文件：

- `src/tui.rs`
- `src/dashboard.rs`
- `src/terminal_image.rs`
- `tests/rust_cli.rs`
- `tests/rust_core.rs`
- `README.md`

验证方式：

```bash
cargo fmt --check
cargo test cli_tui_generates_companion_preview
cargo test cli_live_tui_can_run_bounded_without_alt_screen
cargo test cli_live_tui_can_quit_without_tick_limit
cargo test cli_live_tui_script_can_switch_tabs
cargo test cli_live_tui_can_force_kitty_image_frames
cargo test dashboard_snapshot_and_png_export_are_valid
```

完成标准：

- 静态 TUI 输出包含 Today / Plan / Shop / Fleet / Log。
- 首屏包含当前船、今日任务和路线进度。
- live TUI 可在无 alt screen / 无 raw mode 下跑 bounded 测试。
- live TUI 可通过 `q` 脚本退出。
- Kitty 图片输出有删除序列，退出后不残留图片。

commit 标准：

- commit message 使用 `Complete P1 TUI main screen`。
- 只包含 TUI 主界面、验证文档和必要测试更新。

## P2 宠物船反馈增强

目标：

- 打卡、休息、连续打卡、连续跳过和宝箱/里程碑反馈都能在 CLI/TUI 中明确表达。
- 反馈只解释 deterministic rules 的结果，不额外改规则状态。

范围：

- `done` 后反馈：任务、级别、航程、金币、心情、信任、日志。
- `skip` 后反馈：休息类型、心情变化、宠物船状态、日志。
- 低能量状态和 7 天连续反馈的文案/测试。

不做：

- 不引入额外惩罚。
- 不引入 XP grind。
- 不让 LLM 决定奖励、心情、信任或位置。

涉及文件：

- `src/rules.rs`
- `src/projection.rs`
- `src/cli.rs`
- `src/tui.rs`
- `tests/rust_cli.rs`
- `tests/rust_core.rs`

验证方式：

```bash
cargo fmt --check
cargo test repeated_skip_switches_to_low_energy_without_extra_penalty
cargo test seven_day_streak_changes_companion_feedback_without_extra_coins
cargo test cli_init_done_status_and_log_work
cargo test cli_live_tui_script_can_skip_or_rest
```

完成标准：

- `done` 反馈能说明本次状态变化。
- `skip` 不再只输出裸 `resting`，而是输出可读的休息反馈。
- 重复跳过只进入 low_energy，不追加额外惩罚。
- 连续 7 天触发 happy 反馈，不额外发金币。

commit 标准：

- commit message 使用 `Complete P2 companion feedback`。
- 只包含宠物船反馈、相关规则展示和测试更新。

## P3 计划系统增强

目标：

- 本地轻量计划能支撑日常使用：创建、查看、调整今日任务，并能快速切换到计划中的下一项任务。
- 计划仍通过事件源记录，SQLite 只做 projection。

范围：

- `plan create/show/set-today` 保持稳定。
- 增加安全的高频调整命令，例如从计划任务列表中切到下一项。
- `done` 和 TUI 继续显示 projection 中的今日任务。

不做：

- 不恢复复杂 `plan.yaml`。
- 不做 LLM 自动修改计划。
- 不做医疗诊断或强制训练建议。

涉及文件：

- `src/events.rs`
- `src/rules.rs`
- `src/projection.rs`
- `src/cli.rs`
- `src/tui.rs`
- `tests/rust_cli.rs`
- `tests/rust_core.rs`

验证方式：

```bash
cargo fmt --check
cargo test plan_events_update_daily_task_and_replay
cargo test cli_plan_commands_update_today_task
```

完成标准：

- 计划变更可从 `events.jsonl` 重放恢复。
- 今日任务在 `plan show`、`status --json`、`done` 和 TUI 中一致。
- 新增高频命令不能绕过事件源。

commit 标准：

- commit message 使用 `Complete P3 plan workflow`。
- 只包含计划命令、事件规则和测试更新。

## P4 船只内容管线

目标：

- 内置和用户自定义船只都能通过 catalog + manifest 的管线验证。
- 商店/船坞只接受已注册 catalog 的船只。

范围：

- catalog 加载、冲突检查、assetPath 防逃逸。
- manifest 加载、spritesheetPath 防逃逸、帧范围和动画检查。
- 增加面向用户/发布前检查的验证命令。

不做：

- 不做在线市场。
- 不自动下载远程资产。
- 不恢复全局主题切换。

涉及文件：

- `assets/catalog.json`
- `assets/vessels/*/vessel.json`
- `src/vessels/catalog.rs`
- `src/vessels/manifest.rs`
- `src/vessels/render.rs`
- `src/cli.rs`
- `tests/rust_cli.rs`
- `tests/rust_core.rs`

验证方式：

```bash
cargo fmt --check
cargo test manifest_rejects_path_traversal
cargo test custom_vessel_catalog_and_frame_cache_work
cargo test catalog_purchase_and_equip_replay_as_owned_vessel
cargo test cli_loads_and_sets_custom_vessel
```

完成标准：

- 未注册船只不能进入商店/船坞。
- 用户 catalog 与内置 ID 冲突时失败。
- assetPath 和 spritesheetPath 不能逃逸根目录。
- 可通过 CLI 一键验证 catalog/manifest/基础渲染。

commit 标准：

- commit message 使用 `Complete P4 vessel content pipeline`。
- 只包含船只内容管线、验证命令和测试更新。

## P5 发布与持久化稳定

目标：

- 日常使用和发布前检查有清晰命令。
- 事件源仍是事实来源，SQLite projection 可检查、可重建。
- README 覆盖安装、常用命令、验证和数据目录。

范围：

- 只读配置展示。
- projection 重建或健康检查命令。
- release/install 文档同步。
- 全量测试作为最终门禁。

不做：

- 不做 Homebrew tap 实际发布。
- 不写任意 TOML 字段的危险配置编辑器。
- 不迁移数据目录格式，除非有测试覆盖。

涉及文件：

- `src/cli.rs`
- `src/app.rs`
- `src/config.rs`
- `src/projection.rs`
- `README.md`
- `docs/ROADMAP.md`
- `docs/roadmap/README.md`
- `tests/rust_cli.rs`
- `tests/rust_core.rs`

验证方式：

```bash
cargo fmt --check
cargo test
```

完成标准：

- 用户能查看当前安全配置。
- 用户能验证或重建 projection。
- README 与当前 CLI 行为一致。
- 全量测试通过。

commit 标准：

- commit message 使用 `Complete P5 release persistence stability`。
- 最终 commit 后必须推送远端，并确认 `git status --short --branch` 干净或只剩用户已有未跟踪文件。
