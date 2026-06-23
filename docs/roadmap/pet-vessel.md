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
| dashboard PNG export | 已有，v1.1 已与 TUI 语言统一 |
| 连续休整 low_energy 反馈 | 已有，不额外惩罚 |
| 连续打卡宠物反馈 | 已有，7 天触发 happy，不额外发金币 |
| catalog 注册式多船收集 | 已有 |
| 5 艘内置宠物船 | 已有 |
| ownership / equipped 投影 | 已有 |

## v1.1 已完成

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
- dashboard 文本/PNG 不再暴露 image path/protocol debug，改用 TUI 一致的产品语言。

### 状态机

| 状态 | 触发 | 表现 |
|------|------|------|
| waiting | 初始化后、今日未打卡 | 等待出航 |
| sailing | 完成打卡 | 船在航行 |
| happy | 换船/奖励/连续打卡 | 更明亮、更活跃 |
| resting | 休息日 | 抛锚休息 |
| low_energy | 连续跳过或低心情 | 更慢、更暗 |
| treasure | 奖励/里程碑 | 短庆祝 |

v1.1 规则边界：

- 连续休整或低心情可以触发 `low_energy`。
- `low_energy` 不额外扣金币、信任或心情。
- 连续 7 天打卡可以触发 `happy` 反馈。
- 连续打卡反馈不额外发金币，不引入 XP grind。

### 船只资产

当前 manifest 是基础版。v1.2 开始必须把“渲染资产”和“商店/收集规则”分开。

`vessel.json` 只负责渲染：

```json
{
  "id": "starter_sloop",
  "displayName": "温柔小帆船",
  "spritesheetPath": "spritesheet.png",
  "frame": { "width": 128, "height": 128, "columns": 8, "rows": 4 },
  "animations": {}
}
```

`assets/catalog.json` 负责商店和收集：

```json
{
  "items": [
    {
      "id": "dragon_prow",
      "kind": "vessel",
      "rarity": "uncommon",
      "price": 80,
      "unlock": { "type": "always" },
      "assetPath": "vessels/dragon_prow/vessel.json",
      "tags": ["legacy-naval", "dragon"]
    }
  ]
}
```

必须继续校验：

- spritesheet 路径不得逃逸 vessel 目录。
- frame geometry 非零且不过大。
- animation frame 不越界。
- 缺失 animation 时有 fallback。
- catalog 中的 `assetPath` 不得逃逸 catalog 根目录。
- 未注册 catalog 的船不能进入商店、列表或装备流程。

## v1.2 多船/商店（已完成）

v1.2 的目标不是“多几张图”，而是做成真正的收集闭环：

```text
打卡赚金币 -> shop list 看到船 -> shop buy 购买 -> vessel set 装备 -> TUI 显示当前船
```

### 第一批 5 艘内置船

旧 Python 版已有 `schooner / dragon / ghost / sword / yinglong` 预设。新版不直接恢复旧 theme system，而是保留精神、统一重做为宠物船资产：

| id | 旧预设来源 | 新版定位 | rarity | price |
|------|------|------|------|------|
| `starter_sloop` | `schooner` 初阶帆船 | 默认温柔小帆船 | common | 0 |
| `dragon_prow` | `dragon` 龙头战船 | 进阶龙头战船 | uncommon | 80 |
| `ghost_lantern` | `ghost` 幽灵船 | 夜航幽灵灯船 | rare | 140 |
| `cloudblade_skiff` | `sword` 飞剑 | 云剑小舟 | rare | 220 |
| `yinglong_ark` | `yinglong` 应龙 | 高阶应龙灵舟 | epic | 360 |

第一版全部手工/硬编码资产，不做 LLM 生成。

### 状态模型

事实事件：

```text
ShopItemPurchased { item_id, kind: vessel, cost }
VesselEquipped { vessel_id }
```

SQLite 投影：

```text
owned_items
owned_vessels
equipped_vessel
coins
```

事件源仍然是事实来源，SQLite 必须可以从 `events.jsonl` 重建。

### 商店物品类型

| 类型 | 说明 |
|------|------|
| vessel | 新船 |
| skin | 船只皮肤 |
| decoration | 灯、旗帜、小物件 |
| animation | 特殊待机/庆祝动画 |

v1.2 只实现 `vessel`，但 catalog schema 保留 `kind`，避免后续加皮肤/装饰时重做。

### v1.2 不做

- 不做船只属性加成。所有船第一版都是纯视觉差异。
- 不在 TUI 首屏展示收集进度；首屏只显示当前船。
- 不恢复全局 `naval/cultivation` 主题切换。
- 不做 LLM 生成船只。
- 不做随机掉落或里程碑自动赠送。
- 不做复杂 unlock evaluator；`unlock` 先支持空条件或 `always`。

### 用户自定义船

用户自定义船保留为 experimental：

```text
<home>/catalog.json
<home>/vessels/<id>/vessel.json
<home>/vessels/<id>/spritesheet.png
```

要求：

- 必须在 `<home>/catalog.json` 注册。
- id 不能和内置 catalog 冲突，除非后续明确支持 override。
- 未注册的 `<home>/vessels/<id>` 不再自动进入 `vessel list`。

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
