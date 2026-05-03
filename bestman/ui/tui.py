"""bestman TUI — Textual 全屏终端 UI。

启动 Textual 全屏界面，优先显示 Canvas PNG 像素画（Kitty 终端），
否则回退 ASCII Rich 地图。

使用方式：
    bestman tui
"""

import sys

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Footer, Header, Static
    from textual.binding import Binding
except ImportError:
    raise ImportError(
        "bestman TUI 需要 textual 包。请运行: pip install textual"
    )


def _get_voyage():
    from bestman.core.voyage import Voyage
    return Voyage()


class BestmanApp(App):
    """Textual 全屏终端应用。

    按键：
        D - 打卡   S - 跳过   T - 对话   R - 刷新   Q - 退出
    """

    CSS = """
    Screen {
        background: #081018;
    }

    #map_area {
        height: 1fr;
        margin: 0 1;
        content-align: center middle;
        overflow: auto;
    }

    #status_area {
        dock: bottom;
        height: auto;
        max-height: 6;
        background: #0a1a2a;
        color: #d4d4d4;
        padding: 0 2;
        content-align: left middle;
    }

    #help_bar {
        dock: bottom;
        height: 1;
        background: #0a2a3a;
        color: #808080;
        content-align: center middle;
    }
    """

    BINDINGS = [
        Binding("d", "do_done", "［D］打卡"),
        Binding("s", "do_skip", "［S］跳过"),
        Binding("t", "do_talk", "［T］对话"),
        Binding("r", "do_refresh", "［R］刷新"),
        Binding("q", "quit", "［Q］退出"),
    ]

    def __init__(self):
        super().__init__()
        self._voyage = None

    @property
    def voyage(self):
        if self._voyage is None:
            self._voyage = _get_voyage()
        return self._voyage

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(id="map_area")
        yield Static(id="status_area")
        yield Static(id="help_bar")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(5, self.action_do_refresh)
        self.action_do_refresh()

    # ── 刷新 ─────────────────────────────────────────────────

    def action_do_refresh(self) -> None:
        voyage = self.voyage
        status = voyage.get_status()

        # 地图：优先 Canvas PNG，回退 ASCII
        map_area = self.query_one("#map_area", Static)
        if self._try_canvas(status):
            map_area.update("")  # PNG 已通过 stdout 渲染
        else:
            map_area.update(voyage.render_map())

        # 状态栏
        total = status["total_days"]
        region = status.get("region", status["stage"]["name"])
        coins = status.get("coins", 0)
        streak = status.get("streak", 0)
        tokens = status.get("skip_tokens", 0)

        lines = [
            f"DAY {status['current_day']}/{total} · {region} · 剩余 {status['remaining']} 天"
        ]
        if status["today_done"]:
            lines.append("今日任务已完成 ✓")
        else:
            lines.append(f"今日任务：{voyage.get_daily_task()}")

        coin_str = f"💰 {coins} 金币" if coins else "💰 0 金币"
        streak_str = f"🔥 {streak} 天连击" if streak else "🔥 暂无连击"
        token_str = f"🎫 {tokens} 枚令牌" if tokens else "🎫 0 枚令牌"
        lines.append(f"{coin_str}  {streak_str}  {token_str}")

        self.query_one("#status_area", Static).update("\n".join(lines))
        self.query_one("#help_bar", Static).update(
            "[D] 打卡  [S] 跳过  [T] 对话  [R] 刷新  [Q] 退出"
        )

    def _try_canvas(self, status) -> bool:
        """Try to render Canvas PNG via Kitty protocol. Returns True on success."""
        try:
            from bestman.renderers.canvas import kitty_available, CanvasRenderer, kitty_display
        except ImportError:
            return False

        if not kitty_available():
            return False

        try:
            voyage = self.voyage
            renderer = CanvasRenderer()
            data = voyage.map_engine.build_render_data(
                tiles_revealed=status["tiles_revealed"],
            )
            png = renderer.render_map(
                data=data,
                theme=voyage.theme,
                vessel_def=voyage.theme.vessels.get(voyage.current_vessel),
            )
            # Write Kitty PNG escape to stdout, then move cursor back
            # so Textual can continue rendering below the image
            sys.stdout.write("\033[s")          # save cursor
            sys.stdout.write("\033[2;0H")       # row 2 (below header)
            sys.stdout.flush()
            kitty_display(png, cols=90, rows=24)
            sys.stdout.write("\033[u")          # restore cursor
            sys.stdout.flush()
            return True
        except Exception:
            return False

    # ── 打卡 ─────────────────────────────────────────────────

    def action_do_done(self) -> None:
        voyage = self.voyage
        if voyage.get_status()["today_done"]:
            self.notify("今日已完成 ✓", severity="information")
            return

        result = voyage.complete()
        if result["success"]:
            self.notify(
                f"{result['message']}\n{result['log_entry'][:80]}...",
                title="打卡成功",
                severity="information",
                timeout=5,
            )
            self.action_do_refresh()
        else:
            self.notify(result.get("error", "打卡失败"), severity="error")

    def action_do_skip(self) -> None:
        voyage = self.voyage
        result = voyage.skip()
        if result["success"]:
            self.notify(result["message"], title="跳过", severity="information")
            self.action_do_refresh()
        else:
            self.notify(result.get("error", "无法跳过"), severity="error")

    # ── 对话 ─────────────────────────────────────────────────

    def action_do_talk(self) -> None:
        voyage = self.voyage
        if not voyage.llm.available:
            self.notify("LLM 未配置，请设置 API key", severity="error")
            return

        def _show_prompt(prompt_msg: str) -> str | None:
            """Push a screen that collects a single line of input."""
            from textual.screen import ModalScreen
            from textual.widgets import Input

            class PromptScreen(ModalScreen[str | None]):
                BINDINGS = [Binding("escape", "dismiss_none", "取消")]

                def compose(self):
                    yield Static(prompt_msg, id="prompt_label")
                    yield Input(id="prompt_input")
                    yield Static("Enter 发送，Esc 取消", id="prompt_help")

                def on_mount(self):
                    self.query_one("#prompt_input", Input).focus()

                def on_input_submitted(self, event: Input.Submitted):
                    self.dismiss(event.value or None)

                def action_dismiss_none(self):
                    self.dismiss(None)

            screen = PromptScreen()
            self.push_screen(screen, callback=lambda val: None)

            # Textual runs async; we need to collect result synchronously
            # Use a simple queue-based approach
            import threading
            result_holder = []

            def set_result(val):
                result_holder.append(val)

            self.push_screen(PromptScreen(), set_result)
            # Wait for result (Textual event loop will process this)
            # This won't work synchronously — fall back to app.input()

        # Simpler: use app.input() which is a Textual modal
        import asyncio

        async def _talk_flow():
            msg = await self.input(prompt="与导航员对话（输入 quit 退出）:")
            if not msg or msg.lower() in ("quit", "exit"):
                return
            result = voyage.talk(msg)
            if result["success"]:
                self.notify(
                    result["response"][:500],
                    title="导航员",
                    severity="information",
                    timeout=10,
                )
            else:
                self.notify(result.get("response", "无回应"), title="导航员", severity="warning")

        asyncio.ensure_future(_talk_flow())


def run_tui():
    """Entry point for ``bestman tui``."""
    from bestman.core.config import BESTMAN_HOME

    if not BESTMAN_HOME.is_dir():
        print("bestman 尚未初始化。请先运行 bestman init。")
        raise SystemExit(1)

    app = BestmanApp()
    app.run()
