# 宠物船系统技术路线

> 优先级：最高  
> 目标：让 bestman 的第一注意力从地图转向宠物船

## 核心体验

宠物船是用户每天打卡时看到、关心、互动的对象。

```text
训练完成 -> 船只动起来 -> 状态变好 -> 航线推进 -> 留下一条日志
```

地图只是表达“走了多远”，宠物船表达“今天过得怎么样”。

## 当前状态

| 能力 | 状态 |
|------|------|
| 默认船 `starter_sloop` | 已有 |
| spritesheet + manifest | 已有 |
| idle / waiting / sailing / happy / resting / treasure / low_energy | manifest 已支持 |
| frame cache | 已有 |
| TUI 文本 fallback | 已有 |
| Kitty inline PNG | 已有 |
| preview / animation frame export | 已有 |
| dashboard PNG export | 已有 |

## v1 必做

### TUI 主体验

- 船只区域保持页面最大视觉权重。
- 今日任务必须直接可见。
- 打卡后显示即时反馈：
  - 推进了几天
  - 获得多少金币
  - 船只状态变化
  - 最新日志摘要
- 退出必须可靠：`q` / `Esc` / `Ctrl-C`。
- 图片模式失败时自动退回文本船。

### 状态机

| 状态 | 触发 | 表现 |
|------|------|------|
| waiting | 初始化后、今日未打卡 | 等待出航 |
| sailing | 完成打卡 | 船在航行 |
| happy | 换船/奖励/连续打卡 | 更明亮、更活跃 |
| resting | 休息日 | 抛锚休息 |
| low_energy | 连续跳过或低心情 | 更慢、更暗 |
| treasure | 奖励/里程碑 | 短庆祝 |

### 船只资产

当前 manifest 是基础版。v1.2 扩展：

```json
{
  "id": "starter_sloop",
  "displayName": "温柔小帆船",
  "rarity": "starter",
  "price": 0,
  "unlock": { "type": "default" },
  "spritesheetPath": "spritesheet.png",
  "frame": { "width": 128, "height": 128, "columns": 8, "rows": 4 },
  "animations": {}
}
```

必须继续校验：

- spritesheet 路径不得逃逸 vessel 目录。
- frame geometry 非零且不过大。
- animation frame 不越界。
- 缺失 animation 时有 fallback。

## v1.2 多船/商店

需要把当前简单 `shop buy` 升级成明确模型：

```text
owned_vessels
equipped_vessel
owned_items
```

商店物品类型：

| 类型 | 说明 |
|------|------|
| vessel | 新船 |
| skin | 船只皮肤 |
| decoration | 灯、旗帜、小物件 |
| animation | 特殊待机/庆祝动画 |

短期只需要简单内置船，不急着做生成式资产。

## LLM 资产生成边界

LLM 可以参与：

- 生成船只描述
- 生成 vessel idea
- 生成 spritesheet prompt
- 生成航海日志

LLM 不应直接：

- 写入状态
- 发金币
- 决定解锁
- 绕过 manifest 校验

所有生成资产必须经过本地 manifest 和图片校验。
