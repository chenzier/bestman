"""bestman CLI — Click 命令行入口。

五个命令：
- bestman init     初始化航行
- bestman          仪表盘（默认）
- bestman done     完成今日任务
- bestman log      查看航海日志
- bestman talk     与 AI 导航员对话
"""

import random
import select
import sys
import termios
import time
import tty

import click
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from bestman.config import BESTMAN_HOME, ensure_home, load_config, save_config
from bestman.voyage import Voyage

console = Console()

DICE_FACES = {1: "⚀", 2: "⚁", 3: "⚂"}


def _interactive_roll(console):
    """互动掷骰——用户按键停止滚动。

    Returns:
        int: 掷出的距离 (1-3)
    """
    console.print("按 Enter 掷骰子 🎲")

    # 保存终端设置，切换到 raw mode
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)

    faces = ["⚀", "⚁", "⚂"]
    idx = random.randint(0, 99)  # 随机起点，不可预测

    try:
        tty.setraw(fd)
        while True:
            idx += 1
            face = faces[idx % 3]
            console.print(f"\r   🎲 {face}  按 Enter 停止！  ", end="\r")
            # 非阻塞等待 80ms，检查是否有输入
            ready, _, _ = select.select([sys.stdin], [], [], 0.08)
            if ready:
                sys.stdin.read(1)  # 吃掉按键
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    result = (idx % 3) + 1  # 1, 2, 3
    console.print(" " * 50, end="\r")  # 清空行
    return result


def _roll_dice_animation(distance, description, extra_tiles):
    """掷骰子动画——摇晃 → 减速 → 揭晓，让用户有参与感。

    Args:
        distance: 掷出的距离 (1-3)
        description: 掷骰结果描述文本
        extra_tiles: 手动超额格数
    """
    true_face = DICE_FACES[distance]
    faces = list(DICE_FACES.values())

    # 阶段 1：摇晃 —— 快速切换 6 帧
    for i in range(6):
        face = faces[i % 3]
        console.print(f"     🎲 摇晃中... {face}     ", end="\r")
        time.sleep(0.09)

    # 阶段 2：减速 —— 逐步接近结果
    for i in range(4):
        # 围绕结果附近切换
        offset = (i % 3) - 1
        idx = (distance - 1 + offset) % 3
        face = faces[idx]
        console.print(f"     🎲 即将揭晓... {face}     ", end="\r")
        time.sleep(0.14)

    # 阶段 3：揭晓
    console.print(" " * 40, end="\r")  # 清空动画行

    extra_str = f" + {extra_tiles} 格手动" if extra_tiles else ""
    total = distance + extra_tiles
    console.print(
        f"  🎲 {true_face}  掷出：[bold cyan]{description}[/bold cyan]"
        f"！航行 [bold yellow]{total}[/bold yellow] 海里"
    )


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
    else:
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
    else:
        console.print("[dim]明天再来！运行 [bold green]bestman done[/bold green] 继续航行[/dim]")
    console.print("[dim]运行 [bold green]bestman log[/bold green] 查看航海日志[/dim]")
    console.print("[dim]运行 [bold green]bestman talk[/bold green] 与导航员对话[/dim]")


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
@click.option("-e", "--extra", type=int, default=0, help="手动超额推进格数")
@click.option("--mode", "dice_mode", type=click.Choice(["deterministic", "interactive"]),
              default=None, help="骰子模式（覆盖配置）")
def done(extra, dice_mode):
    """完成今日任务，掷骰子推进 1-3 格。

    每天只能完成一次。完成后会生成航海日志并检查里程碑。
    LLM 可用时生成独特叙事，不可用时退回模板。

    使用 --mode interactive 开启互动掷骰：数字快速刷新，
    按键停止，惊喜感和参与度更高。

    \b
    示例：
        bestman done                        # 正常掷骰推进
        bestman done -e 2                   # 掷骰结果 + 额外 2 格
        bestman done --mode interactive     # 互动掷骰模式
        bestman done --mode deterministic   # 确定性掷骰模式
    """
    _require_init()

    voyage = Voyage()
    mode = dice_mode or voyage.config.get("dice", {}).get("mode", "deterministic")

    if mode == "interactive":
        # 互动模式流程：LLM 调用 → 用户掷骰 → 记录
        with console.status("[cyan]导航员正在撰写航海日志...[/cyan]"):
            # 先检查今天是否已打卡，不掷骰
            pass

        distance = _interactive_roll(console)
        desc = voyage._get_distance_description(distance)
        face = DICE_FACES[distance]
        console.print(f"🎲 {face}  掷出：[bold cyan]{desc}[/bold cyan]！航行 [bold yellow]{distance + extra}[/bold yellow] 海里")

        with console.status("[cyan]导航员正在撰写航海日志...[/cyan]"):
            result = voyage.complete(extra_tiles=extra, distance=distance)
    else:
        # 确定性模式（当前流程）
        with console.status("[cyan]导航员正在撰写航海日志...[/cyan]"):
            result = voyage.complete(extra_tiles=extra)

    if not result["success"]:
        console.print(f"[yellow]{result['error']}[/yellow]")
        console.print("[dim]明天再来吧！[/dim]")
        return

    if mode != "interactive":
        # 掷骰子动画——用户参与的核心体验（仅确定性模式播放动画）
        dice = result["dice"]
        _roll_dice_animation(dice["distance"], dice["description"], dice["extra_tiles"])
    console.print()

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
        total = status["total_days"]
        actual_days = status["completed_days"]
        if actual_days < total:
            early_text = (
                f"🎉 提前抵达！只用了 {actual_days} 天就完成了 {total} 天的航程。\n"
                "探索模式开启：你可以继续打卡，或者休息庆祝。"
            )
        else:
            early_text = (
                f"🎉 你已抵达新大陆！\n"
                f"{total} 天的航海之旅圆满结束。\n"
                "你可以站在婚礼上，自信而挺拔。"
            )
        console.print(
            Panel(
                f"[bold yellow]{early_text}[/bold yellow]",
                title="航程结束",
                border_style="yellow",
            )
        )
        console.print()


@main.group()
def config():
    """管理 bestman 配置。

    \b
    示例：
        bestman config dice-mode              # 查看当前骰子模式
        bestman config dice-mode interactive  # 切换到互动掷骰
        bestman config dice-mode deterministic # 切换到确定性掷骰
    """
    _require_init()


@config.command("dice-mode")
@click.argument("mode", required=False, type=click.Choice(["deterministic", "interactive"]))
def config_dice_mode(mode):
    """查看或设置骰子模式。

    bestman config dice-mode              # 查看当前模式
    bestman config dice-mode interactive  # 切换到互动模式
    """
    if mode:
        # 设置模式
        cfg = load_config()
        cfg.setdefault("dice", {})["mode"] = mode
        save_config(cfg)
        mode_names = {"deterministic": "确定性", "interactive": "互动"}
        console.print(f"[green]骰子模式已切换为：{mode_names.get(mode, mode)}（{mode}）[/green]")
    else:
        # 查看模式
        cfg = load_config()
        current = cfg.get("dice", {}).get("mode", "deterministic")
        mode_names = {"deterministic": "确定性", "interactive": "互动"}
        console.print(f"当前骰子模式：[bold cyan]{mode_names.get(current, current)}[/bold cyan]（{current}）")


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
