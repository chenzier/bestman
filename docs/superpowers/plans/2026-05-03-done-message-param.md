# bestman done -m 手动航行日志 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `bestman done` 添加 `-m`/`--message` 参数，允许用户手动输入航行日志内容，跳过 LLM/模板生成。

**Architecture:** CLI 层新增 `-m` 选项传给 `voyage.complete()`，`complete()` 中判断 `message` 非空时直接用用户输入替代 LLM/模板生成。其余逻辑（骰子、金币、事件、宝藏、里程碑）完全不变。

**Tech Stack:** Python, Click, pytest

---

### Task 1: voyage.py — `complete()` 接收 `message` 参数

**Files:**
- Modify: `bestman/voyage.py:147-170`（签名 + 日志分支）

- [ ] **Step 1: 添加 message 参数并修改日志生成分支**

在 `complete()` 方法签名（第 147 行）加 `message=None`：

```python
def complete(self, date_str=None, extra_tiles=0, force=False, distance=None, message=None) -> dict:
```

在日志生成逻辑（第 269-277 行）加 `message` 判断分支，把原来的代码包进 `else`：

```python
        # 生成日志：-m 手动输入优先，否则 LLM → fallback 到模板
        llm_used = False
        if message is not None:
            log_entry = message
        else:
            stage_name = get_current_stage(current_day, self.config)["name"]
            remaining = max(0, self.config["voyage"]["total_days"] - current_day)
            task_done = self.config["voyage"]["default_daily_task"]

            log_entry = generate_voyage_log(
                self.llm, stage_name, remaining, current_day, task_done
            )
            if log_entry is not None:
                llm_used = True
            else:
                log_entry = get_log_entry(current_day)

        self.state.save_log(date_str, log_entry)
```

- [ ] **Step 2: 运行 voyage 测试确认通过**

```bash
uv run pytest tests/test_voyage.py -v
```

Expected: 全部 PASS（现有测试不应受影响）。

- [ ] **Step 3: 添加 voyage 单元测试：手动 message 路径**

在 `tests/test_voyage.py` 的 `TestComplete` 类中添加：

```python
def test_complete_with_manual_message(self, mock_deps):
    """-m 参数传入手动日志文本，跳过 LLM 和模板。"""
    mock_deps["state"].today_recorded.return_value = False
    mock_deps["state"].get_tiles_revealed.side_effect = [0, 1]

    voyage = Voyage()
    result = voyage.complete("2026-05-03", message="今天下雨改室内，俯卧撑 50×3")

    assert result["success"] is True
    assert result["log_entry"] == "今天下雨改室内，俯卧撑 50×3"
    assert result["llm_used"] is False
    # 不应调用 LLM 或模板
    mock_deps["gen_log"].assert_not_called()
    mock_deps["get_log"].assert_not_called()
```

- [ ] **Step 4: 运行新测试确认失败**

```bash
uv run pytest tests/test_voyage.py::TestComplete::test_complete_with_manual_message -v
```

Expected: FAIL（`message` 参数还不存在）。

- [ ] **Step 5: 运行新测试确认通过**

```bash
uv run pytest tests/test_voyage.py::TestComplete::test_complete_with_manual_message -v
```

Expected: PASS。

- [ ] **Step 6: 运行全部 voyage 测试**

```bash
uv run pytest tests/test_voyage.py -v
```

Expected: 全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add bestman/voyage.py tests/test_voyage.py
git commit -m "feat: add message param to Voyage.complete() for manual log entry

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: cli.py — `done` 命令加 `-m` 选项

**Files:**
- Modify: `bestman/cli.py:290-296`（选项 + 传参）
- Modify: `tests/test_cli.py:218+`（CLI 测试）

- [ ] **Step 1: 添加 -m 选项并传给 complete()**

在 `done` 命令的 `@click.option` 列表末（第 295 行后）加一行：

```python
@click.option("-m", "--message", default=None, help="手动输入航行日志内容")
```

在确定性模式分支（第 332-333 行）和互动模式分支（第 329 行）的 `voyage.complete(...)` 调用中加 `message=message`：

确定性模式：
```python
result = voyage.complete(date_str=date_str, extra_tiles=extra, force=force, message=message)
```

互动模式：
```python
result = voyage.complete(date_str=date_str, extra_tiles=extra, force=force, distance=distance, message=message)
```

- [ ] **Step 2: 运行 CLI 测试确认不能通过**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: 现有 done 测试 FAIL（因为 mock 的 `complete()` 会收到新的 `message` 关键字参数）。

- [ ] **Step 3: 更新 CLI mock 断言以接受新参数**

`tests/test_cli.py` 中 `test_done_success` 方法（第 237-241 行）的断言需要改为接受 `message=None`：

```python
        result = runner.invoke(main, ["done"])

        assert result.exit_code == 0
        assert "掷出" in result.output
        assert "晨光洒在甲板上" in result.output
        mock_voyage["inst"].complete.assert_called_once()
        call_kwargs = mock_voyage["inst"].complete.call_args.kwargs
        assert call_kwargs.get("message") is None
```

添加一个手动 message 的 CLI 测试：

```python
    @patch("bestman.cli.BESTMAN_HOME")
    def test_done_with_manual_message(self, mock_home, mock_voyage, runner):
        """done -m 传入手动日志。"""
        mock_home.is_dir.return_value = True
        mock_voyage["inst"].complete.return_value = {
            "success": True,
            "message": "完成！推进了 1 格",
            "tiles_revealed": 1,
            "log_entry": "室内俯卧撑 50×3，汗流浃背",
            "milestone": None,
            "error": None,
            "llm_used": False,
            "dice": {"distance": 1, "description": "风平浪静", "extra_tiles": 0},
        }

        result = runner.invoke(main, ["done", "-m", "室内俯卧撑 50×3，汗流浃背"])

        assert result.exit_code == 0
        assert "室内俯卧撑" in result.output
        mock_voyage["inst"].complete.assert_called_once()
        call_kwargs = mock_voyage["inst"].complete.call_args.kwargs
        assert call_kwargs["message"] == "室内俯卧撑 50×3，汗流浃背"
```

- [ ] **Step 4: 运行 CLI 测试确认通过**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: 全部 PASS。

- [ ] **Step 5: 运行全部测试**

```bash
uv run pytest tests/ -v
```

Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add bestman/cli.py tests/test_cli.py
git commit -m "feat: add -m/--message option to bestman done for manual log entry

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```
