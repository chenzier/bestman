# bestman done -m 手动航行日志

## 需求

`bestman done` 加 `-m` 参数，允许用户手动输入航行日志内容，替代自动生成的叙事日志。

## 范围

- 只替换 **narrative** 类型日志（原本由 LLM/模板生成的那条）
- 事件日志和宝藏日志保持不变（它们本来就是离线的）
- 骰子、金币、里程碑、地图渲染等所有其他逻辑不变

## 改动

### cli.py — `done` 命令

- 新增 `-m`/`--message` 选项（`type=str`, `default=None`）
- 传递给 `voyage.complete(message=message)`

### voyage.py — `complete()` 方法

- 签名新增 `message=None` 参数
- 叙事日志分支：
  - `message is not None` → 直接用 `message`，`llm_used=False`
  - `message is None` → 走原有 LLM → 模板回退逻辑

## 示例

```
bestman done -m "今天下雨改练室内俯卧撑，50×3，汗流浃背"
```
