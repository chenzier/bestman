"""bestman TUI — Textual 全屏终端 UI。

启动 Textual 全屏界面，显示 Canvas 地图（或 ASCII 回退）、
状态信息和快捷按键交互。

使用方式：
    bestman tui                 # 或 python -m bestman.ui.tui
"""

from datetime import date

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Footer, Header, Static, Button
    from textual.binding import Binding
except ImportError:
    raise ImportError(
        "bestman TUI 需要 textual 包。请运行: pip install textual"
    )


def _get_voyage():
    """Lazy import to avoid circular deps."""
    from bestman.core.voyage import Voyage
    return Voyage()


class StatusBar(Static):
    """Bottom status bar showing coins, streak, tokens."""

    def render(self):
        return ""  # rendered by parent


class BestmanApp(App):
    """Textual 全屏终端应用。

    按键：
        D - 打卡
        S - 跳过
        T - 对话
        R - 刷新
        Q - 退出
    """

    CSS = """
    Screen {
        background: #081018;
    }

    #header {
        dock: top;
        height: 3;
        background: #0a2a3a;
        color: #4ec9b0;
        text-style: bold;
        content-align: center middle;
    }

    #footer {
        dock: bottom;
        height: 1;
        background: #0a2a3a;
        color: #808080;
    }

    #map_area {
        height: 1fr;
        margin: 0 1;
        content-align: center middle;
        overflow: auto;
    }

    #map_text {
        color: #86d4ff;
        text-style: none;
    }

    #status_area {
        dock: bottom;
        height: 3;
        background: #0a1a2a;
        color: #d4d4d4;
        padding: 0 2;
        content-align: left middle;
    }

    #help_bar {
        dock: bottom;
        height: 3;
        background: #0a2a3a;
        color: #808080;
        content-align: center middle;
    }

    #talk_input {
        dock: bottom;
        height: 3;
        background: #0a2a3a;
        color: #e0e0e0;
        border: solid #4ec9b0;
    }

    Button {
        margin: 0 1;
    }

    #dialog {
        background: #0a2a3a 80%;
        border: solid #4ec9b0;
        padding: 1 2;
        width: 60%;
        height: auto;
        max-height: 50%;
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
        self._talking = False

    @property
    def voyage(self):
        if self._voyage is None:
            self._voyage = _get_voyage()
        return self._voyage

    def compose(self) -> ComposeResult:
        """Build the UI layout."""
        yield Header(show_clock=True)
        yield Static(id="map_area")
        yield Static(id="status_area")
        yield Static(id="help_bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initial data load."""
        self.set_interval(5, self.do_refresh)
        self.do_refresh()

    def action_do_refresh(self) -> None:
        """Refresh the dashboard display."""
        voyage = self.voyage
        status = voyage.get_status()

        # Build rich text map
        map_text = voyage.render_map()
        self.query_one("#map_area", Static).update(map_text)

        # Build status text
        total = status["total_days"]
        region = status.get("region", status["stage"]["name"])
        coins = status.get("coins", 0)
        streak = status.get("streak", 0)
        tokens = status.get("skip_tokens", 0)

        status_lines = []
        status_lines.append(
            f"DAY {status['current_day']}/{total} · {region} · 剩余 {status['remaining']} 天"
        )
        if status["today_done"]:
            status_lines.append("今日任务已完成 ✓")
        else:
            status_lines.append(f"今日任务：{voyage.get_daily_task()}")

        coin_str = f"💰 {coins} 金币" if coins else "💰 0 金币"
        streak_str = f"🔥 {streak} 天连击" if streak else "🔥 暂无连击"
        token_str = f"🎫 {tokens} 枚令牌" if tokens else "🎫 0 枚令牌"
        status_lines.append(f"{coin_str}  {streak_str}  {token_str}")

        self.query_one("#status_area", Static).update("\n".join(status_lines))

        # Build help bar
        help_text = "[D] 打卡  [S] 跳过  [T] 对话  [R] 刷新  [Q] 退出"
        self.query_one("#help_bar", Static).update(help_text)

    def action_do_done(self) -> None:
        """Complete today's task."""
        voyage = self.voyage
        status = voyage.get_status()
        if status["today_done"]:
            self.notify("今日已完成 ✓", severity="information")
            return

        result = voyage.complete()
        if result["success"]:
            self.notify(
                f"🎲 {result['message']}\n{result['log_entry'][:80]}...",
                title="打卡成功",
                severity="information",
                timeout=5,
            )
            self.do_refresh()
        else:
            self.notify(result.get("error", "打卡失败"), severity="error")

    def action_do_skip(self) -> None:
        """Use a skip token."""
        voyage = self.voyage
        result = voyage.skip()
        if result["success"]:
            self.notify(result["message"], title="跳过", severity="information")
            self.do_refresh()
        else:
            self.notify(result.get("error", "无法跳过"), severity="error")

    def action_do_talk(self) -> None:
        """Open talk dialog."""
        voyage = self.voyage
        if not voyage.llm.available:
            self.notify("LLM 未配置，请设置 API key", severity="error")
            return

        self._talking = True
        try:
            msg = self._prompt_input("与导航员对话（输入 quit 退出）:")
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
                self.notify(result["response"], title="导航员", severity="warning")
        finally:
            self._talking = False

    def _prompt_input(self, prompt: str) -> str:
        """Show an input dialog and return the user's text.

        Since Textual's built-in Input widget is complex to use in a
        notification context, we fall back to `app.input()` (a modal).
        """
        import asyncio

        async def _get_input():
            return await self.input(prompt=prompt, password=False)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(_get_input())


def run_tui():
    """Entry point for ``bestman tui``."""
    from bestman.core.config import BESTMAN_HOME

    if not BESTMAN_HOME.is_dir():
        print("bestman 尚未初始化。请先运行 bestman init。")
        raise SystemExit(1)

    app = BestmanApp()
    app.run()
