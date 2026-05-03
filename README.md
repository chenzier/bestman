# bestman

航向新大陆 — 175 天的航海健身之旅。

一个 Python CLI 工具。每天完成最小门槛任务 → 在多雾像素地图上前进一格 → 内置航海日志。

**目标：** 2026 年 10 月 25 日抵达新大陆，作为伴郎自信地站在婚礼上。

## 架构

```
bestman/           ← CLI 源码（产品本体）
~/.bestman/        ← 运行时数据
```

## Demo 命令

| 命令 | 作用 |
|------|------|
| `bestman init` | 初始化航行 |
| `bestman` | 查看仪表盘（像素地图 + 今日任务 + 进度） |
| `bestman done` | 完成今日任务，推进一格 |
| `bestman log` | 查看航海日志 |

## 安装

```bash
cd bestman
uv sync
```

见 `docs/superpowers/plans/2026-05-03-bestman-route-c.md`
