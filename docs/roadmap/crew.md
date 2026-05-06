# 船员系统 技术路线

> 版本：v2.0（进行中）

---

## 核心体验定位

船员系统的核心价值不在养成数值，在**陪伴感和叙事累积**：

1. **对话触发** → 每天打卡后船员随机发言，被关心、被看见
2. **角色人设** → 不同名字、过去、性格的船员，不只是职业标签
3. **里程碑史诗** → 第三人称编年史，船员互动构成共同的冒险故事

用户的长期感受：_"我走过了很多路，一件事一件事加起来，仿佛是一件壮举。"_

---

## 角色（Role）与人设（Character）— 两层分离

```
角色（Role）          人设（Character）
─────────────        ─────────────────
船长                  沉稳老陈（老练、用航海隐喻）
                     暴躁独眼（粗犷、每句话带"小子"）
                     温柔小周（年轻、有点理想主义）

厨子                  铁锅老李（热情、讲食物故事）
                     毒舌阿九（嘴损但手艺好）

队医                  中医张叔（温和、专业）
                     冷面小林（话少但一针见血）
```

用户先通过 role 选择职能（招募时），然后每个 role 下有多种可解锁/可选的人设。同一艘船上不能有两个相同 role 的船员。

人设决定了：对话模板池、性格标注、在史诗中的叙事风格。

### 人设 YAML 模板

人设通过 YAML 文件定义，内置在 `bestman/personas/`，用户自定义在 `~/.bestman/personas/`。加载优先级：用户 > 内置。

```yaml
# ~/.bestman/personas/captain_old_chen.yaml
persona_id: "old_chen"
role: "captain"
name: "老陈"
rarity: "common"
personality: "沉稳老练，每条建议都带航海隐喻"
backstory: "三十年的老水手，年轻时在南洋跑过香料船。左手缺一根指头，从不提怎么丢的。"
speaking_style: "慢条斯理，每句话前习惯性'嗯'一声"

dialogue_patterns:
  - trigger: "completed_day"
    responses:
      - "嗯。今天的航程不错。明天继续保持这个方向。"
      - "干得漂亮，小子。我在你这个年纪，还没你一半坚持。"
  - trigger: "struggle"
    responses:
      - "累了就看看海——比你累的人多了去了，但他们也到了对岸。"
  - trigger: "idle"
    responses:
      - "（老陈靠在舵轮上，用仅剩的四根手指敲着木头）"
  - trigger: "port_arrival"
    responses:
      - "港口到了。下去走走？船我看着。"
  - trigger: "milestone"
    responses:
      - "{name}。我在海上见过无数人，能走到这里的，不多。"

special_skill:
  name: "老船长的直觉"
  description: "每次出港时额外获得 10 金币补给"
  cooldown_days: 7
  effect_type: "port_bonus"
```

### PersonaLoader（新增 `bestman/core/persona.py`）

- `load_all()` → 扫描所有 YAML 文件，合并内置 + 用户
- `load(persona_id)` → 加载单个人设
- `validate(persona_dict)` → 校验必填字段（persona_id、role、name、dialogue_patterns）

---

## 船长 — 默认免费船员

船长是每个用户默认拥有的免费船员，初始人设随机（可后续更换）。`bestman talk` 始终和船长对话：

```
$ bestman talk
你> 膝盖不舒服，静蹲做不了
船长（老陈）：收到。接下来 3 天我把静蹲换成坐姿抬腿——
              对膝盖压力小，同样练股四头肌。
              （计划已更新：静蹲 → 坐姿抬腿，3 天后自动恢复）
```

船长职责：
- **训练计划**：`bestman talk` 制定/调整训练方案
- **日常导航**：`bestman done` 后的叙事日志
- **主动关心**：完成打卡后主动提问

---

## 可招募船员

| 角色 | 功能 | 价格 | 稀有度 |
|------|------|------|--------|
| 船长 | 训练计划、done 叙事、`talk` 入口 | 免费 | 初始 |
| 厨子 | `bestman eat` 饮食记录、食谱建议 | ~20 金币 | common |
| 队医 | 伤病咨询、体重反馈、疼痛关心 | ~100 金币 | rare |
| 水手长 | 动作指导、超额训练鼓励 | ~200 金币 | rare |
| 瞭望手 | 前方预报、海域描述 | ~300 金币 | legendary |

---

## 被动成长

**不由用户操作，不花金币。** 等级随相处时间和共同经历自然增长，上限 5 级。

| 等级 | 触发条件 | 效果 |
|------|----------|------|
| Lv1 | 刚上船 | 基础对话池 A |
| Lv2 | 共处 10 天 | — |
| Lv3 | 共处 20 天 | 对话池 B（开始提过往事件、带名字称呼） |
| Lv4 | 共处 40 天 | — |
| Lv5 | 共处 60 天 + 至少 1 次里程碑 | 对话池 C（老友口吻、内部笑话、callback） |

升级感知不靠进度条——靠对话语气和史诗叙事中自然流露的深度差异。

---

## 情绪系统 — 三档

仅影响对话语气，不影响核心功能。

| 档位 | 状态 | 触发 |
|------|------|------|
| 昂扬 | 积极、有活力 | 连续打卡多日 |
| 平静 | 日常状态 | 默认 |
| 低落 | 话少、需要关心 | 连续漏打卡 |

---

## 对话触发

| 触发场景 | 概率 | 发言者 |
|----------|------|--------|
| `bestman done` | 70% | 船长（叙事） + 随机 1 名在船船员 |
| `bestman done` 后主动提问 | 70% | 船长 |
| `bestman eat` | 100% | 厨子 |
| 连续打卡 7 天 | 100% | 随机在船船员 |
| 到达里程碑 | 100% | 全体船员依次发言 |
| 连续 3 天未打卡 | 100% | 船长（关心） |
| `bestman talk` | 100% | 船长 |
| 港口到达 | 100% | 船长 + 随机船员 |
| 港口离开 | 50% | 瞭望手（前方预报） |

---

## crew talk LLM 增强

当前是纯模板驱动。改造方向：

- **LLM 优先，模板回退**：离线时用模板
- **上下文注入**：注入人设、情绪、最近 5 条对话、航行状态
- **双向对话**：船员发言→用户可选回复→LLM 深度对话→直接回车结束

```
[厨子（老李）] 训练完了吧？厨房炖了一锅鱼汤——蛋白质正好。
你> 今天练得特别累
[厨子（老李）] 累就对了。来，先喝汤。我加了姜——去寒。
              明天要是还累，跟我说，我让船长减点量。
你> （直接回车，结束对话）
```

---

## 里程碑史诗

每次到达里程碑时，生成第三人称航海编年史。

**生成方式：LLM + 事实注入。** 系统注入摘要（打卡天数、体重变化、船员互动统计、金币变化），LLM 基于真实历史编故事，确保不凭空瞎编。

史诗存入 `voyage_logs`，`log_type = "epic"`。

---

## 金币消费

| 消费方式 | 金币 | 说明 |
|----------|------|------|
| 定向招募 | 角色定价 | 直接招募指定 role |
| 随机招募（扭蛋） | 50（首抽）/ 100 | 稀有度随机，含保底 |
| 更换人设 | ~50 | 为已拥有的船员更换 character |
| 召回解雇船员 | 原价 × 80% | 折扣召回 |
| 解雇退款 | 原价 × 50% | 传奇船员退 30% |

---

## CLI 命令

```bash
bestman crew hire <role>           # 定向招募
bestman crew recruit               # 随机招募（扭蛋）
bestman crew list                  # 当前在船船员
bestman crew talk <name>           # 和指定船员对话
bestman crew persona <role>        # 查看该角色可用人设
bestman crew persona <role> <id>   # 切换人设（消耗金币）
bestman crew persona install <f>   # 安装自定义人设 YAML
bestman crew fire <name>           # 解雇船员
bestman crew recall <name>         # 召回已解雇船员
```

---

## 需要砍掉的内容

当前 `crew.py` 中已实现但不符合设计方向：

| 模块 | 原因 |
|------|------|
| `upgrade()` / `add_xp()` 手动升级 | 改为被动成长，不花金币 |
| `check_quest_progress()` 每周任务 | 任务系统给用户压力 |
| `generate_weekly_quests()` | 同上 |
| XP 数值追踪 | 不再需要，等级仅看天数和里程碑 |
| 情绪精确数值（0-100） | 简化为三档 |
| `boost_mood()` / `update_moods()` 复杂逻辑 | 同上 |

---

## 数据库改动

```sql
-- crew 表加字段
persona_id   TEXT     -- 当前人设 ID
days_active  INTEGER  -- 累计活跃天数（升级依据）
milestones_witnessed INTEGER

-- crew 表移除
xp           -- 不再需要
-- mood 改为三档枚举

-- 移除表
crew_quests
```

---

## 港口系统（关联船员）

### 定位
每 5 + random(0, 20) 天触发一次港口访问。确定性随机（复用 events.py 模式：`Random(day * 997 + 13 + 42)`）。

### 港口流程

```
🚢 第 47 天 — 抵达「三桅港」

灯塔在薄雾里闪烁。码头边停着几艘渔船，空气里飘着烤鱼的烟。

[船长（老陈）] 到了。要不要下去走走？船我看着。
                    或者歇一天——明天再航也不迟。

你可以：
  🏪 进商店     bestman port shop
  👥 招募船员   bestman port recruit
  🚢 看新船只   bestman port ships
  😴 休息一天   bestman port rest       （不扣连击）
  ⛵ 直接启航   bestman done
```

### 港口新增触发类型

| 触发器 | 发言者 |
|--------|--------|
| `port_arrival` | 船长 + 随机船员 |
| `port_departure` | 瞭望手（前方预报） |
| `port_rest` | 厨子（"好好歇，明天给你做好吃的"） |

### 数据表

```sql
CREATE TABLE port_visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    port_name TEXT NOT NULL,
    arrival_date TEXT NOT NULL,
    departure_date TEXT,
    rested INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
)
```

### 港口商店道具

| 道具 | 金币 | 效果 |
|------|------|------|
| 回复药水 | 30 | 当天额外掷骰 +1 |
| 幸运符 | 50 | 下次打卡宝藏概率翻倍 |
| 精准罗盘 | 80 | 下次掷骰保底 2 格 |
| 朗姆酒（礼物） | 20 | 送船员，情绪提升 |
| 新鲜食材 | 15 | 厨子特饮效果翻倍 |
