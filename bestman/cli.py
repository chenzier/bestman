"""bestman CLI — Click 命令行入口。

六个命令：
- bestman init     初始化航行
- bestman          仪表盘（默认）
- bestman done     完成今日任务
- bestman skip     使用跳过令牌
- bestman plan     查看航行计划
- bestman log      查看航海日志
- bestman talk     与 AI 导航员对话
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from bestman.config import BESTMAN_HOME, ensure_home
from bestman.voyage import Voyage

console = Console()


def _require_init():
    """检查 bestman 是否已初始化，未初始化则报错退出。"""
    if not BESTMAN_HOME.is_dir():
        console.print(
            "[bold red]bestman 尚未初始化[/bold red]\n\n"
            "请先运行 [bold green]bestman init[/bold green] 来开始你的航行。"
        )
        raise SystemExit(1)


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """bestman — 航向新大陆

    175 天的航海健身之旅。
    """
    if ctx.invoked_subcommand is None:
        _require_init()
        _dashboard()


def _dashboard():
    """渲染仪表盘。"""
    voyage = Voyage()
    status = voyage.get_status()

    # Rule 头
    console.print(Rule("[bold cyan]bestman — 航向新大陆[/bold cyan]"))
    console.print()

    # 地图
    console.print(voyage.render_map())
    console.print()

    # 进度条
    tiles = status["tiles_revealed"]
    total = status["total_days"]
    percent = min(100, int(tiles / total * 100))
    bar_width = 30
    filled = int(bar_width * tiles / total) if total > 0 else 0
    empty = bar_width - filled

    stage_name = status["stage"]["name"]
    console.print(
        f"DAY {status['current_day']}/{total} · "
        f"[bold yellow]{stage_name}[/bold yellow] · "
        f"剩余 {status['remaining']} 天"
    )

    bar = "[bold green]" + "█" * filled + "[dim]" + "░" * empty + "[/dim]"
    console.print(f"{bar} {tiles}/{total}")

    console.print()

    # 今日任务
    if status["today_done"]:
        console.print("[bold green]今日任务已完成 ✓[/bold green]")

    # 连击和令牌
    streak = status.get("streak", 0)
    tokens = status.get("skip_tokens", 0)
    streak_icons = f"[bold yellow]🔥 {streak} 天连击[/bold yellow]" if streak > 0 else "[dim]暂无连击[/dim]"
    token_icons = f"[bold cyan]🎫 {tokens} 枚令牌[/bold cyan]" if tokens > 0 else "[dim]0 枚令牌[/dim]"
    console.print(f"{streak_icons}  {token_icons}")

    if not status["today_done"]:
        console.print(f"今日任务：[bold cyan]{voyage.get_daily_task()}[/bold cyan]")

    console.print()

    # 最近日志
    logs = voyage.get_logs(3)
    if logs:
        console.print("[dim]最近航海日志：[/dim]")
        for entry in logs:
            text = entry["text"]
            if len(text) > 100:
                text = text[:100] + "…"
            console.print(f"  [dim]{entry['date']}:[/dim] {text}")
    else:
        console.print("[dim]尚无航海日志。完成第一次打卡后，日志将出现在这里。[/dim]")

    console.print()

    # 命令提示
    if not status["today_done"]:
        console.print("[dim]运行 [bold green]bestman done[/bold green] 完成今日任务[/dim]")
        if tokens > 0:
            console.print(f"[dim]运行 [bold cyan]bestman skip[/bold cyan] 使用令牌跳过（{tokens} 枚可用）[/dim]")
    else:
        console.print("[dim]明天再来！运行 [bold green]bestman done[/bold green] 继续航行[/dim]")
    console.print("[dim]运行 [bold green]bestman log[/bold green] 查看航海日志[/dim]")
    console.print("[dim]运行 [bold green]bestman talk[/bold green] 与导航员对话[/dim]")


def _render_plan_view(voyage):
    """渲染航行计划概览：全部 7 个阶段、里程碑与进度。"""
    status = voyage.get_status()
    tiles = status["tiles_revealed"]
    current_day = status["current_day"]

    # 头
    console.print()
    console.print("[bold cyan]⚓ 航行计划 — 175 天航向新大陆[/bold cyan]")
    streak = status.get("streak", 0)
    streak_part = f" · [bold yellow]🔥 {streak} 天连击[/bold yellow]" if streak > 0 else ""
    console.print(
        f"  当前：DAY {current_day}/175 · "
        f"[bold yellow]{status['stage']['name']}[/bold yellow] · "
        f"剩余 {status['remaining']} 天{streak_part}"
    )
    console.print()

    stages = voyage.config["voyage"]["stages"]
    milestones = voyage.config["voyage"]["milestones"]

    for stage in stages:
        start, end = stage["days"]
        stage_length = end - start + 1
        name = stage["name"]

        # 阶段状态
        is_completed = tiles >= end
        is_current = start <= (tiles + 1) <= end

        if is_completed:
            icon = "[bold green]✓[/bold green]"
            name_style = "bold green"
            bar_color = "bold green"
            completed_in_stage = stage_length
        elif is_current:
            icon = "[bold yellow]◆[/bold yellow]"
            name_style = "bold yellow"
            bar_color = "bold yellow"
            completed_in_stage = max(0, tiles - start + 1)
        else:
            icon = "[dim]◇[/dim]"
            name_style = "dim"
            bar_color = "dim"
            completed_in_stage = 0

        # 阶段内进度条
        bar_width = 15
        filled = int(bar_width * completed_in_stage / stage_length) if stage_length > 0 else 0
        empty = bar_width - filled
        bar = f"[{bar_color}]" + "█" * filled + "░" * empty + "[/]"

        # 里程碑
        milestone_name = milestones.get(end)
        milestone_text = f"[dim]✦ 里程碑：DAY {end} · {milestone_name}[/dim]" if milestone_name else ""

        console.print(f"  {icon} [{name_style}]{name}[/{name_style}]  DAY {start}-{end}  [{bar}] {completed_in_stage}/{stage_length}")
        if milestone_text:
            console.print(f"    {milestone_text}")

    console.print()
    console.print("[dim]计划源自 bestman init 时配置的航程。[/dim]")
    console.print()


@main.command()
def plan():
    """查看航行计划（所有阶段与里程碑）。

    显示全部 7 个阶段的日程、进度条与里程碑，
    清晰标记当前所在阶段。
    """
    _require_init()
    voyage = Voyage()
    _render_plan_view(voyage)


@main.command()
def init():
    """初始化 bestman 航行。

    创建 ~/.bestman/ 目录和默认配置文件。
    """
    ensure_home()
    console.print()
    console.print("[bold cyan]⚓ bestman 号已就绪[/bold cyan]")
    console.print(f"[dim]航线：2026-05-03 → 2026-10-25[/dim]")
    console.print(f"[dim]航程：175 天[/dim]")
    console.print(f"[dim]每日必定任务：死虫式 3×10 + 静蹲 2×30秒[/dim]")
    console.print(f"[dim]数据目录：{BESTMAN_HOME}[/dim]")
    console.print()
    console.print("[dim]运行 [bold green]bestman[/bold green] 查看仪表盘[/dim]")


@main.command()
def done():
    """完成今日任务，推进一格。

    每天只能完成一次。完成后会生成航海日志并检查里程碑。
    LLM 可用时生成独特叙事，不可用时退回模板。
    """
    _require_init()

    voyage = Voyage()

    # 仿 hermes 的 Rich spinner 加载态
    with console.status("[cyan]正在撰写今日航海日志...[/cyan]"):
        result = voyage.complete()

    if not result["success"]:
        console.print(f"[yellow]{result['error']}[/yellow]")
        console.print("[dim]明天再来吧！[/dim]")
        return

    console.print()
    console.print(f"[bold green]✓ {result['message']}[/bold green]")
    if result.get("llm_used"):
        console.print("[dim]（日志由 AI 导航员生成）[/dim]")
    console.print()

    # 日志
    tiles = result["tiles_revealed"]
    status = voyage.get_status()
    stage_name = status["stage"]["name"]
    console.print(f"Day {tiles} · [bold yellow]{stage_name}[/bold yellow]")
    console.print(f"[cyan]{result['log_entry']}[/cyan]")
    console.print()

    # 里程碑
    if result["milestone"]:
        console.print(
            f"[bold magenta]✦ 里程碑达成：{result['milestone']}！[/bold magenta]"
        )
        console.print()

    # 事件
    if result.get("event"):
        evt = result["event"]
        console.print()
        if evt["type"] == "bonus_tile":
            console.print(f"[bold yellow]🎉 {evt['message']}[/]")
        elif evt["type"] == "encouragement":
            console.print(f"[cyan]✨ {evt['message']}[/]")
        elif evt["type"] == "challenge":
            console.print(f"[yellow]💪 {evt['message']}[/]")
        console.print()

    # 地图更新
    tiles = result["tiles_revealed"]
    total = status["total_days"]
    rule_text = f"⚓ 第 {tiles} 天 · {stage_name}"
    console.print(Rule(rule_text, style="dim cyan"))
    console.print(voyage.render_map())
    console.print()

    if result["tiles_revealed"] >= status["total_days"]:
        console.print(
            Panel(
                "[bold yellow]🎉 你已抵达新大陆！[/bold yellow]\n"
                "175 天的航海之旅圆满结束。\n"
                "你可以站在婚礼上，自信而挺拔。",
                title="航程结束",
                border_style="yellow",
            )
        )
        console.print()


@main.command()
def skip():
    """使用跳过令牌，休息一天但不中断连击。

    消耗一枚跳过令牌来记录今天的训练（不推进地图）。
    连续打卡 7 天可获得一枚跳过令牌。
    """
    _require_init()

    voyage = Voyage()
    result = voyage.skip()

    if not result["success"]:
        console.print(f"[yellow]{result['error']}[/yellow]")
        console.print("[dim]连续打卡 7 天即可获得一跳过令牌。[/dim]")
        return

    console.print()
    console.print(f"[bold cyan]✓ {result['message']}[/bold cyan]")
    console.print()
    console.print(f"[dim]{result['log_entry']}[/dim]")
    console.print()
    console.print("[dim]连击已保，明天继续前行！[/dim]")


@main.command()
@click.option("-n", "--count", default=10, help="显示最近的 N 条日志")
def log(count):
    """查看航海日志。"""
    _require_init()

    voyage = Voyage()
    logs = voyage.get_logs(count)

    console.print()
    console.print(Rule("[bold cyan]航海日志[/bold cyan]"))

    if not logs:
        console.print()
        console.print("[dim]尚无航海日志。完成第一次打卡后记录将出现在这里。[/dim]")
    else:
        for entry in logs:
            console.print()
            console.print(f"[bold yellow]{entry['date']}[/bold yellow]")
            console.print(f"[cyan]{entry['text']}[/cyan]")

    console.print()


@main.command()
@click.option("-m", "--message", default=None, help="单次对话消息（不进入循环模式）")
def talk(message):
    """与 AI 导航员对话。

    仿 hermes cli.py 的交互循环模式（轻量版：用 console.input 代替 prompt_toolkit）。

    无参数时进入对话循环模式（输入 quit/exit/back 退出）。
    使用 -m 参数进行单次对话。

    \b
    示例：
        bestman talk                  # 进入对话循环
        bestman talk -m "今天好累"     # 单次对话
    """
    _require_init()

    voyage = Voyage()

    if not voyage.llm.available:
        console.print("[red]LLM 未配置[/red]")
        console.print(
            "[dim]请在 [bold]~/.bestman/.env[/bold] 中设置 OPENAI_API_KEY[/dim]"
        )
        return

    # 单次对话模式
    if message is not None:
        with console.status("[cyan]导航员正在思考...[/cyan]"):
            result = voyage.talk(message)
        if result["success"]:
            console.print()
            console.print(f"[cyan]导航员：{result['response']}[/cyan]")
        else:
            console.print(f"[yellow]{result['response']}[/yellow]")
        return

    # 对话循环模式
    console.print()
    console.print(Rule("[bold cyan]与导航员对话[/bold cyan]"))
    console.print()
    console.print("[dim]输入 [bold]quit[/bold]/[bold]exit[/bold]/[bold]back[/bold] 结束对话[/dim]")
    console.print()

    # 开场白
    with console.status("[cyan]导航员正在思考...[/cyan]"):
        intro = voyage.talk("你好，我是水手。今天航行怎么样？")
    if intro["success"]:
        console.print(f"[cyan]导航员：{intro['response']}[/cyan]")
    else:
        console.print(f"[yellow]{intro['response']}[/yellow]")
        return
    console.print()

    while True:
        try:
            msg = console.input("[yellow]你> [/yellow]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        if not msg:
            continue
        if msg.lower() in ("quit", "exit", "back"):
            console.print("[dim]导航员：风向正好，随时回来。[/dim]")
            break

        with console.status("[cyan]导航员正在思考...[/cyan]"):
            result = voyage.talk(msg)
        if result["success"]:
            console.print(f"[cyan]导航员：{result['response']}[/cyan]")
        else:
            console.print(f"[yellow]{result['response']}[/yellow]")
        console.print()
