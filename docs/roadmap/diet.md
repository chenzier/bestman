# 饮食管理 技术路线

> 版本：v2.0（绑定厨子船员）

---

## 定位

不做独立命令体系，厨子上船后 `bestman eat` 可用。不追踪卡路里，不审判，不制造焦虑。

```
$ bestman eat "午餐：鸡胸肉沙拉 + 糙米饭"
🥗 已记录
厨子（老李）：鸡胸肉和糙米饭——蛋白质和慢碳的组合。
俺在海上最珍视这样的补给，能撑到黄昏不饿。

$ bestman eat "下午：没忍住吃了一包薯片"
🥗 已记录
厨子（老李）：一包薯片是一阵突风，不会让船偏离航线。
下次饿的时候，厨房里有提前备好的坚果。
```

---

## 数据层

```sql
CREATE TABLE meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    meal_text TEXT NOT NULL,
    meal_type TEXT DEFAULT 'snack',  -- breakfast/lunch/dinner/snack
    created_at TEXT DEFAULT (datetime('now'))
)
```

---

## 逻辑层（voyage.py）

- `record_meal(text, meal_type=None, date_str=None)` → 写库，如果厨子在船上触发对话
- `get_meals(date_str=None, limit=10)` → 按日期查
- `get_weekly_meal_summary()` → 本周饮食概览
- 厨子对话：`bestman eat` → 100% 触发厨子发言（LLM 优先，模板回退）

---

## AI 层（llm.py）

```python
def meal_comment(client, meal_text, cook_persona, recent_meals):
    """基于厨子人设 + 最近 3 条饮食记录 + 航行状态，生成 1-2 句反馈。
    原则：不追踪卡路里，不审判，不制造焦虑，用航海意象。"""
```

---

## CLI

```bash
bestman eat "午餐：鸡胸肉沙拉 + 糙米饭"
bestman eat --type breakfast "燕麦粥 + 鸡蛋"
bestman eat --week                    # 查看本周饮食概览
```

---

## 对话触发

| 触发 | 概率 | 发言者 |
|------|------|--------|
| `bestman eat` | 100% | 厨子 |
| 连续 3 天未 eat | 50% | 厨子（关心："这两天没见你来厨房"） |

---

## 新增触发类型

厨子的 `dialogue_patterns` 扩展：

- `meal_recorded` — 饮食记录后的反馈
- `meal_healthy` — 健康饮食（LLM 判断）
- `meal_junk` — 不那么健康的饮食
- `meal_missed_day` — 连续未记录饮食
