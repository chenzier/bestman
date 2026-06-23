# 其他 backlog

> 优先级：按 v1 主线稳定度重新评估

## LLM

当前 Rust 版已有 mock narrative 和 OpenAI-compatible LLM 航海日志接口。

已落地：

- 航海日志生成。
- provider/model/prompt version 配置。
- template fallback。
- LLM 失败不阻断打卡。

后续接入顺序：

1. 每周/月度温柔回顾。
2. 训练计划建议。
3. 船只描述或资产 prompt。

硬边界：

- template fallback 必须存在。
- 保存 provider/model/prompt version。
- 不让 LLM 直接改状态。
- 失败不阻断打卡。

## 工坊/自定义资产

v1.2 开始，所有船只必须通过 catalog 注册。

内置资产：

```text
assets/catalog.json
assets/vessels/<id>/vessel.json
```

用户自定义资产保留为 experimental：

```text
<home>/catalog.json
<home>/vessels/<id>/vessel.json
```

未注册 catalog 的 `vessel.json` 不进入商店、列表或装备流程。

后续可做：

- vessel import/export。
- manifest validator CLI。
- spritesheet preview。
- 社区分享格式。

暂缓：

- 在线市场。
- 自动下载安装到本地。
- 远程代码/脚本资产。

## 里程碑史诗

可以作为 v3 叙事增强：

- 到达里程碑时触发。
- 注入真实数据：打卡天数、最长 streak、体重变化、已拥有船只。
- LLM 生成第三人称编年史。
- 存入事件或日志 projection。

暂不引入复杂吟游诗人系统。

## 发布

v1 已有：

- `bestman` 命令指向 Rust 版。
- README 不再要求用户长期使用 `cargo run`。

后续需要：

- 二进制 release 包。
- macOS 安装脚本或 Homebrew tap。
- 数据目录升级说明。

## 配置与重置

当前 Rust 版主要依赖 `config.toml` 和 `--home`。

已落地：

- `bestman reset --yes`：只清空当前 `--home`，必须显式确认。

需要补：

- `bestman config show`：只读展示安全配置。
- 高频配置命令：例如默认任务、总天数、休息日。

暂缓：

- dice-mode 配置。
- 大型交互式配置编辑器。
- 任意 TOML 字段命令行写入。

## 骰子、随机事件、主题

旧 Python 版的骰子、随机事件和主题系统不直接迁移。

处理方向：

- 骰子：当前 1-3 是宠物船节奏占位；如恢复 1-6，需要重新平衡奖励和动画反馈。
- 互动掷骰：只有在它能增强参与感且不拖慢打卡时再做。
- 随机事件：必须 deterministic，可从事件重放恢复，不允许只存在于渲染阶段。
- 主题：先扩船只资产和皮肤，不恢复全局 naval/cultivation 主题切换。

## 社区

社区、主题市场、船只市场都属于远期。只有在本地资产模型稳定后再设计。
