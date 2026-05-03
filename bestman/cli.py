"""bestman CLI — Click 命令行入口。

命令：
- bestman init     初始化航行
- bestman          仪表盘（默认）
- bestman done     完成今日任务
- bestman skip     使用跳过令牌
- bestman plan     查看航行计划
- bestman log      查看航海日志
- bestman talk     与 AI 导航员对话
- bestman reset    重置所有数据
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

DICE_FACES = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}


def _interactive_roll(console, base_weights=None):
    """互动掷骰——数字高频刷新，用户按键停止。

    屏幕快速滚动 1-6，按任意键停止后用加权随机决定结果：
    - 1-3 按配置权重分配（默认 60/30/10）
    - 4 概率 6%、5 概率 5%、6 概率 3%

    Args:
        console: Rich Console 实例
        base_weights: [w1, w2, w3] 权重列表，合计 100

    Returns:
        int: 掷出的距离 (1-6)
    """
    if base_weights is None:
        base_weights = [60, 30, 10]

    # 构建加权概率分布：1-3 占 86%，4-6 分别占 6/5/3%
    w1, w2, w3 = base_weights
    base_total = w1 + w2 + w3
    scale = 0.86
    probs = [
        (w1 / base_total) * scale,  # 1
        (w2 / base_total) * scale,  # 2
        (w3 / base_total) * scale,  # 3
        0.06,                        # 4
        0.05,                        # 5
        0.03,                        # 6
    ]

    console.print("按任意键掷骰子 🎲")

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    idx = random.randint(0, 99)

    try:
        tty.setraw(fd)
        while True:
            idx += 1
            num = (idx % 6) + 1  # 屏幕只显示数字 1-6，不用骰子表情
            console.print(f"\r   🎲 [ {num} ]  按任意键停止！  ", end="\r")
            ready, _, _ = select.select([sys.stdin], [], [], 0.06)
            if ready:
                sys.stdin.read(1)
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    # 加权随机决定最终结果
    result = random.choices(range(1, 7), weights=probs, k=1)[0]
    console.print(" " * 50, end="\r")
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

    # 2D 世界地图
    console.print(voyage.render_map())
    console.print()

    # 状态行
    total = status["total_days"]
    region = status.get("region", status["stage"]["name"])
    console.print(
        f"DAY {status['current_day']}/{total} · "
        f"[bold yellow]{region}[/bold yellow] · "
        f"剩余 {status['remaining']} 天"
    )
    console.print()

    # 今日任务
    if status["today_done"]:
        console.print("[bold green]今日任务已完成 ✓[/bold green]")

    # 连击和令牌
    coins = status.get("coins", 0)
    streak = status.get("streak", 0)
    tokens = status.get("skip_tokens", 0)
    coin_icons = f"[bold yellow]💰 {coins} 金币[/bold yellow]" if coins > 0 else "[dim]💰 0 金币[/dim]"
    streak_icons = f"[bold yellow]🔥 {streak} 天连击[/bold yellow]" if streak > 0 else "[dim]暂无连击[/dim]"
    token_icons = f"[bold cyan]🎫 {tokens} 枚令牌[/bold cyan]" if tokens > 0 else "[dim]0 枚令牌[/dim]"
    console.print(f"{coin_icons}  {streak_icons}  {token_icons}")

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
    coins = status.get("coins", 0)
    streak = status.get("streak", 0)
    coins_part = f" · [bold yellow]💰 {coins} 金币[/bold yellow]" if coins > 0 else ""
    streak_part = f" · [bold yellow]🔥 {streak} 天连击[/bold yellow]" if streak > 0 else ""
    console.print(
        f"  当前：DAY {current_day}/175 · "
        f"[bold yellow]{status['stage']['name']}[/bold yellow] · "
        f"剩余 {status['remaining']} 天{coins_part}{streak_part}"
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
@click.option("-e", "--extra", type=int, default=0, help="手动超额推进格数")
@click.option("-f", "--force", is_flag=True, help="强制重新打卡（覆盖当日记录，仅测试用）")
@click.option("-d", "--date", "date_str", default=None, help="指定日期 YYYY-MM-DD（测试用）")
@click.option("--mode", "dice_mode", type=click.Choice(["deterministic", "interactive"]),
              default=None, help="骰子模式（覆盖配置）")
@click.option("-m", "--message", default=None, help="手动输入航行日志内容")
def done(extra, force, date_str, dice_mode, message):
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

        weights = voyage.config.get("dice", {}).get("weights", [60, 30, 10])
        distance = _interactive_roll(console, base_weights=weights)
        desc = voyage._get_distance_description(distance)
        face = DICE_FACES[distance]
        console.print(f"🎲 {face}  掷出：[bold cyan]{desc}[/bold cyan]！航行 [bold yellow]{distance + extra}[/bold yellow] 海里")

        with console.status("[cyan]导航员正在撰写航海日志...[/cyan]"):
            result = voyage.complete(date_str=date_str, extra_tiles=extra, force=force, distance=distance, message=message)
    else:
        # 确定性模式（当前流程）
        with console.status("[cyan]导航员正在撰写航海日志...[/cyan]"):
            result = voyage.complete(date_str=date_str, extra_tiles=extra, force=force, message=message)

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
    region = status.get("region", status["stage"]["name"])
    console.print(f"Day {tiles} · [bold yellow]{region}[/bold yellow]")
    console.print(f"[cyan]{result['log_entry']}[/cyan]")
    console.print()

    # 金币获取
    if result.get("coins") and result["coins"].get("breakdown"):
        coins = result["coins"]
        breakdown_str = " + ".join(
            f"[yellow]{v} 金币[/yellow] [dim]({k})[/dim]"
            for k, v in coins["breakdown"].items()
            if not k.startswith("💎")  # treasure coins shown separately
        )
        if breakdown_str:
            console.print(f"💰 [bold yellow]+{coins['total']} 金币[/bold yellow]  ({breakdown_str})")
            console.print()

    # 宝藏
    if result.get("treasures"):
        for treasure in result["treasures"]:
            console.print(f"💎 [bold yellow]发现了{treasure['name']}！[/bold yellow] +{treasure['coins']} 金币")
            console.print(f"[dim]{treasure['message']}[/dim]")
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
    rule_text = f"⚓ 第 {tiles} 天 · {region}"
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
@click.option("-y", "--yes", is_flag=True, help="跳过确认，直接重置")
def reset(yes):
    """重置所有航行数据。

    清空打卡记录、航海日志、跳过令牌和宝藏。
    需要手动确认以防范误操作。
    """
    _require_init()

    voyage = Voyage()

    # 统计现有数据
    days_count = len(voyage.state.conn.execute("SELECT 1 FROM days").fetchall())
    logs_count = len(voyage.state.conn.execute("SELECT 1 FROM voyage_logs").fetchall())
    tokens_count = voyage.state.get_available_skip_tokens()
    tokens_used = len(voyage.state.conn.execute("SELECT 1 FROM skip_tokens WHERE used=1").fetchall())
    treasures_count = len(voyage.state.conn.execute("SELECT 1 FROM treasures").fetchall())
    total_tokens = tokens_count + tokens_used

    if days_count == 0 and logs_count == 0 and total_tokens == 0 and treasures_count == 0:
        console.print("[dim]没有数据需要重置。[/dim]")
        return

    console.print()
    console.print("[bold red]⚠ 即将重置所有数据[/bold red]")
    console.print()
    console.print(f"  打卡记录：[yellow]{days_count} 天[/yellow]")
    console.print(f"  航海日志：[yellow]{logs_count} 条[/yellow]")
    console.print(f"  跳过令牌：[yellow]{total_tokens} 枚[/yellow]（可用 {tokens_count}，已用 {tokens_used}）")
    console.print(f"  宝藏记录：[yellow]{treasures_count} 条[/yellow]")
    console.print()
    console.print("[bold red]此操作不可撤销！[/bold red]")
    console.print()

    if yes:
        confirmed = True
    else:
        confirmed = click.confirm("确认重置？输入 yes 继续", default=False, show_default=True)

    if not confirmed:
        console.print("[dim]已取消重置。[/dim]")
        return

    voyage.state.reset_all()
    console.print()
    console.print("[green]✓ 所有数据已重置[/green]")
    console.print("[dim]航行记录已清空，可以从头开始。[/dim]")
    console.print()


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
