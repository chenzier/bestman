"""bestman CLI — Click 命令行入口（薄路由层）。

所有 Rich 输出逻辑已提取到 _views.py。
本模块仅负责 CLI 路由、参数解析和用户交互逻辑。
"""

import random
import select
import sys
import termios
import time
import tty
from datetime import date, timedelta

import click
from rich.console import Console

from bestman.config import BESTMAN_HOME, ensure_home, load_config, save_config, load_plan, save_plan
from bestman.ui._views import (
    handle_plan_override,
    render_dashboard,
    render_done,
    render_map_view,
    render_plan_show,
    render_progress,
    render_review,
    render_vessel_list,
)

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
            num = (idx % 6) + 1
            console.print(f"\r   🎲 [ {num} ]  按任意键停止！  ", end="\r")
            ready, _, _ = select.select([sys.stdin], [], [], 0.06)
            if ready:
                sys.stdin.read(1)
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

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
        offset = (i % 3) - 1
        idx = (distance - 1 + offset) % 3
        face = faces[idx]
        console.print(f"     🎲 即将揭晓... {face}     ", end="\r")
        time.sleep(0.14)

    # 阶段 3：揭晓
    console.print(" " * 40, end="\r")

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
        from bestman.core.voyage import Voyage
        render_dashboard(console, Voyage())


@main.command()
def map_cmd():
    """查看航行地图概览（所有阶段与里程碑）。

    显示全部阶段的日程、进度条与里程碑，
    清晰标记当前所在阶段。
    """
    _require_init()
    from bestman.core.voyage import Voyage
    render_map_view(console, Voyage())


@main.command()
def init():
    """初始化 bestman 航行。

    创建 ~/.bestman/ 目录和配置文件，让你设置自己的航行参数。
    """
    from rich.rule import Rule

    console.print()
    console.print(Rule("[bold cyan]⚓ bestman 初始化[/bold cyan]"))
    console.print()
    console.print("[dim]欢迎登船！先帮你配置航行参数。[/dim]")
    console.print()

    # 1. 航行周期
    total_days = click.prompt(
        "航行周期（天）",
        type=int,
        default=120,
        show_default=True,
    )
    console.print()

    # 2. 每日训练
    console.print("每日训练任务是什么？")
    console.print("[dim]示例：深蹲 3×15 + 平板支撑 3×30秒[/dim]")
    console.print("[dim]留空则设为「未设置」（稍后可用 bestman plan create 制定计划）[/dim]")
    daily_task = click.prompt(
        "每日任务",
        default="",
        show_default=False,
    )
    if not daily_task.strip():
        daily_task = "未设置 — 运行 bestman plan create 制定计划"
    console.print()

    # 3. LLM 配置
    console.print(Rule("[dim]AI 导航员配置（可选）[/dim]"))
    console.print()
    console.print("[dim]AI 导航员可以帮你写航海日志、制定健身计划、在对话中调整训练。[/dim]")
    console.print("[dim]支持 OpenAI 兼容接口（DeepSeek、OpenAI、OpenRouter 等）。[/dim]")
    console.print("[dim]不配置也能正常使用——日志会用模板生成，部分功能受限。[/dim]")
    console.print()
    llm_configured = False
    if click.confirm("是否现在配置 AI 导航员？", default=True):
        api_key = click.prompt(
            "API Key",
            default="",
            show_default=False,
        )
        if api_key.strip():
            base_url = click.prompt(
                "API Base URL",
                default="https://api.deepseek.com",
                show_default=True,
            )
            model = click.prompt(
                "模型名称",
                default="deepseek-chat",
                show_default=True,
            )
            # 写入 ~/.bestman/.env
            env_path = BESTMAN_HOME / ".env"
            env_path.write_text(
                f"# bestman LLM 配置\n"
                f"OPENAI_API_KEY={api_key.strip()}\n"
                f"OPENAI_BASE_URL={base_url.strip()}\n"
                f"LLM_MODEL={model.strip()}\n"
            )
            llm_configured = True
            console.print()
            console.print("[green]✓ AI 导航员已配置[/green]")
        else:
            console.print("[dim]已跳过，稍后可在 [bold]~/.bestman/.env[/bold] 中手动配置。[/dim]")
    else:
        console.print("[dim]已跳过，稍后可在 [bold]~/.bestman/.env[/bold] 中手动配置。[/dim]")
    console.print()

    # 4. 计算日期
    today = date.today()
    end_date = today + timedelta(days=total_days)

    # 写入配置
    ensure_home()
    cfg = load_config()
    cfg["voyage"]["total_days"] = total_days
    cfg["voyage"]["end_date"] = end_date.isoformat()
    cfg["voyage"]["default_daily_task"] = daily_task
    save_config(cfg)

    # 欢迎信息
    console.print("[bold cyan]⚓ bestman 号已就绪[/bold cyan]")
    console.print(f"[dim]航线：{today.isoformat()} → {end_date.isoformat()}[/dim]")
    console.print(f"[dim]航程：{total_days} 天[/dim]")
    console.print(f"[dim]每日任务：{daily_task}[/dim]")
    if llm_configured:
        console.print(f"[dim]AI 导航员：[green]已配置[/green][/dim]")
    else:
        console.print(f"[dim]AI 导航员：[yellow]未配置[/yellow]（稍后编辑 ~/.bestman/.env）[/dim]")
    console.print(f"[dim]数据目录：{BESTMAN_HOME}[/dim]")
    console.print()
    console.print("[dim]运行 [bold green]bestman[/bold green] 查看仪表盘[/dim]")
    if not llm_configured:
        console.print(
            "[dim]运行 [bold green]bestman plan create[/bold green] 制定详细健身计划（需先配置 LLM）[/dim]"
        )


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

    from bestman.core.voyage import Voyage
    voyage = Voyage()
    mode = dice_mode or voyage.config.get("dice", {}).get("mode", "deterministic")

    if mode == "interactive":
        with console.status("[cyan]导航员正在撰写航海日志...[/cyan]"):
            pass

        weights = voyage.config.get("dice", {}).get("weights", [60, 30, 10])
        distance = _interactive_roll(console, base_weights=weights)
        desc = voyage._get_distance_description(distance)
        face = DICE_FACES[distance]
        console.print(f"🎲 {face}  掷出：[bold cyan]{desc}[/bold cyan]！航行 [bold yellow]{distance + extra}[/bold yellow] 海里")

        with console.status("[cyan]导航员正在撰写航海日志...[/cyan]"):
            result = voyage.complete(date_str=date_str, extra_tiles=extra, force=force, distance=distance, message=message)
    else:
        with console.status("[cyan]导航员正在撰写航海日志...[/cyan]"):
            result = voyage.complete(date_str=date_str, extra_tiles=extra, force=force, message=message)

    if not result["success"]:
        console.print(f"[yellow]{result['error']}[/yellow]")
        console.print("[dim]明天再来吧！[/dim]")
        return

    dice = result.get("dice") or {}
    total_advance = dice.get("distance", 0) + dice.get("extra_tiles", 0)

    if mode != "interactive":
        _roll_dice_animation(dice["distance"], dice["description"], dice["extra_tiles"])
    console.print()

    render_done(console, voyage, result, total_advance, mode)

    # 船员对话
    crew_msg = result.get("crew_dialogue")
    if crew_msg:
        console.print(f"[bold cyan][{crew_msg['name']}][/bold cyan] {crew_msg['text']}")
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
        cfg = load_config()
        cfg.setdefault("dice", {})["mode"] = mode
        save_config(cfg)
        mode_names = {"deterministic": "确定性", "interactive": "互动"}
        console.print(f"[green]骰子模式已切换为：{mode_names.get(mode, mode)}（{mode}）[/green]")
    else:
        cfg = load_config()
        current = cfg.get("dice", {}).get("mode", "deterministic")
        mode_names = {"deterministic": "确定性", "interactive": "互动"}
        console.print(f"当前骰子模式：[bold cyan]{mode_names.get(current, current)}[/bold cyan]（{current}）")


@config.command("theme")
@click.argument("theme_name", required=False)
def config_theme(theme_name):
    """查看或设置主题。

    bestman config theme              # 查看当前主题和可用主题
    bestman config theme cultivation  # 切换到田园主题
    """
    from bestman.themes import list_themes, get_theme

    cfg = load_config()
    current_theme = cfg.get("voyage", {}).get("theme", "naval")

    if theme_name:
        # Validate that the theme exists
        available_themes = list_themes()

        if theme_name not in available_themes:
            console.print(f"[red]未知主题：{theme_name}[/red]")
            console.print(f"[dim]可用主题：{', '.join(available_themes)}[/dim]")
            return

        # Get current vessel in case we need to handle compatibility
        current_vessel = cfg.get("profile", {}).get("vessel", "schooner")

        # Load the new theme to check if current vessel exists in it
        new_theme = get_theme(theme_name)

        # If current vessel doesn't exist in new theme, switch to default vessel
        if current_vessel not in new_theme.vessels:
            # Find a suitable default vessel in the new theme
            if new_theme.vessels:
                default_vessel = next(iter(new_theme.vessels.keys()))
                cfg.setdefault("profile", {})["vessel"] = default_vessel
                console.print(f"[yellow]载具不兼容，已自动切换为 {new_theme.vessels[default_vessel].icon} {new_theme.vessels[default_vessel].name}[/yellow]")
            else:
                # No vessels in theme, use default
                cfg.setdefault("profile", {})["vessel"] = "schooner"

        # Update theme
        cfg.setdefault("voyage", {})["theme"] = theme_name
        save_config(cfg)
        console.print(f"[green]✓ 主题已切换为：{theme_name}[/green]")
    else:
        # Show current theme and available themes
        available_themes = list_themes()
        console.print(f"当前主题：[bold cyan]{current_theme}[/bold cyan]")
        console.print("可用主题：")
        for theme in available_themes:
            marker = "[bold yellow]●[/bold yellow]" if theme == current_theme else " "
            console.print(f"  {marker} [cyan]{theme}[/cyan]")


@config.command("vessel")
@click.argument("vessel_id", required=False)
def config_vessel(vessel_id):
    """查看或设置载具。

    bestman config vessel        # 查看当前载具和可用载具
    bestman config vessel sword  # 切换到剑客号载具
    """
    from bestman.core.voyage import Voyage
    from bestman.themes import get_theme
    voyage = Voyage()
    current_vessel = voyage.current_vessel
    theme = voyage.theme

    owned = set(voyage.config.get("profile", {}).get("vessel_owned", ["schooner"]))

    if vessel_id:
        if vessel_id not in theme.vessels:
            available = ", ".join(theme.vessels.keys())
            console.print(f"[red]未知载具：{vessel_id}[/red]")
            console.print(f"[dim]可用载具：{available}[/dim]")
            return

        if vessel_id not in owned:
            vdef = theme.vessels[vessel_id]
            console.print(f"[yellow]你尚未拥有 {vdef.icon} {vdef.name}。[/yellow]")
            console.print(f"[dim]需要 {vdef.price} 金币购买。[/dim]")
            return

        cfg = load_config()
        cfg.setdefault("profile", {})["vessel"] = vessel_id
        save_config(cfg)

        vdef = theme.vessels[vessel_id]
        console.print(f"[green]✓ 载具已切换为 {vdef.icon} {vdef.name}[/green]")
        console.print("[dim]运行 [bold green]bestman[/bold green] 查看仪表盘。[/dim]")
        console.print()
    else:
        # Show current vessel and available vessels in current theme
        console.print(f"当前主题：[bold cyan]{theme.name}[/bold cyan]")
        console.print()

        if not theme.vessels:
            console.print("[dim]当前主题没有可用载具。[/dim]")
            console.print()
            return

        for vid, vdef in theme.vessels.items():
            is_current = vid == current_vessel
            is_owned = vid in owned
            marker = "[bold yellow]●[/bold yellow]" if is_current else " "
            icon = vdef.icon
            name = vdef.name
            if is_current:
                status = "[bold green]（当前）[/bold green]"
            elif not is_owned and vdef.price > 0:
                status = f"[dim]（{vdef.price} 金币）[/dim]"
            else:
                status = "[dim]（已拥有）[/dim]"
            console.print(f"  {marker} {icon}  [bold cyan]{name}[/bold cyan]  {status}")

        current_def = theme.vessels.get(current_vessel)
        current_name = current_def.name if current_def else "?"
        current_icon = current_def.icon if current_def else "?"
        console.print()
        console.print(f"[dim]当前载具：[bold]{current_icon} {current_name}[/bold][/dim]")
        console.print("[dim]切换载具：[bold green]bestman config vessel <ID>[/bold green][/dim]")
        console.print()


@config.command("show")
def config_show():
    """显示当前配置。
    """
    from bestman.core.voyage import Voyage

    cfg = load_config()

    console.print()
    console.print("[bold cyan]当前配置[/bold cyan]")
    console.print("=" * 30)

    # Show theme
    theme_name = cfg.get("voyage", {}).get("theme", "naval")
    console.print(f"主题：[bold]{theme_name}[/bold]")

    # Show vessel
    vessel_id = cfg.get("profile", {}).get("vessel", "schooner")
    voyage = Voyage()
    theme = voyage.theme
    vessel_def = theme.vessels.get(vessel_id)
    if vessel_def:
        console.print(f"载具：[bold]{vessel_def.icon} {vessel_def.name}[/bold] ({vessel_id})")
    else:
        console.print(f"载具：[bold]{vessel_id}[/bold]")

    # Show dice mode
    dice_mode = cfg.get("dice", {}).get("mode", "deterministic")
    mode_names = {"deterministic": "确定性", "interactive": "互动"}
    console.print(f"骰子模式：[bold]{mode_names.get(dice_mode, dice_mode)} ({dice_mode})[/bold]")

    # Show owned vessels
    owned = cfg.get("profile", {}).get("vessel_owned", ["schooner"])
    console.print(f"已拥有载具：[bold]{', '.join(owned)}[/bold]")

    console.print()


@main.group()
def plan():
    """管理健身计划。

    \b
    示例：
        bestman plan create     # 交互式创建新计划
        bestman plan show       # 查看当前计划
        bestman plan edit        # 用编辑器修改计划
    """
    _require_init()


@plan.command("create")
def plan_create():
    """交互式制定健身计划。

    回答几个问题，导航员（LLM）会为你生成分阶段计划，
    并保存到 ~/.bestman/plan.yaml。
    """
    _require_init()

    from bestman.core.voyage import Voyage
    from rich.rule import Rule

    console.print()
    console.print(Rule("[bold cyan]制定健身计划[/bold cyan]"))
    console.print()

    voyage = Voyage()
    if not voyage.llm.available:
        console.print("[red]LLM 未配置[/red]")
        console.print(
            "[dim]请在 [bold]~/.bestman/.env[/bold] 中设置 OPENAI_API_KEY[/dim]"
        )
        return

    existing = load_plan()
    if existing:
        console.print(f"[yellow]已存在计划：{existing.get('name', '未知')}[/yellow]")
        console.print()

    answers = {}

    console.print("你的目标是什么？")
    goal_choices = {
        "1": ("weight_loss", "减肥"),
        "2": ("muscle_gain", "增肌"),
        "3": ("habit", "养成运动习惯"),
        "4": ("custom", "自定义"),
    }
    for key, (_, label) in goal_choices.items():
        console.print(f"  [bold][{key}][/bold] {label}")
    goal_choice = click.prompt(">", type=click.Choice(["1", "2", "3", "4"]), default="1")
    answers["goal_type"] = goal_choices[goal_choice][0]

    if answers["goal_type"] == "custom":
        custom_goal = click.prompt("描述你的目标", default="")
        answers["custom_goal"] = custom_goal

    console.print()

    weight_input = click.prompt("当前体重？（kg，回车跳过）", default="", show_default=False)
    answers["start_weight_kg"] = float(weight_input) if weight_input.strip() else None
    if answers["start_weight_kg"] is not None:
        target_input = click.prompt("目标体重？（kg，回车跳过）", default="", show_default=False)
        answers["target_weight_kg"] = float(target_input) if target_input.strip() else None
    else:
        answers["target_weight_kg"] = None

    console.print()

    answers["total_days"] = click.prompt("计划周期？（天）", type=int, default=120)
    console.print()

    console.print("你现在的运动基础？")
    fitness_choices = {
        "1": ("beginner", "几乎不运动"),
        "2": ("occasional", "偶尔运动（每周 1-2 次）"),
        "3": ("intermediate", "有一定基础"),
    }
    for key, (_, label) in fitness_choices.items():
        console.print(f"  [bold][{key}][/bold] {label}")
    fitness_choice = click.prompt(">", type=click.Choice(["1", "2", "3"]), default="1")
    answers["fitness_level"] = fitness_choices[fitness_choice][0]

    console.print()

    console.print("运动偏好？")
    pref_choices = {
        "1": ("bodyweight", "居家自重（深蹲、静蹲、平板支撑）"),
        "2": ("outdoor", "户外（跑步、爬楼梯）"),
        "3": ("mixed", "混合"),
    }
    for key, (_, label) in pref_choices.items():
        console.print(f"  [bold][{key}][/bold] {label}")
    pref_choice = click.prompt(">", type=click.Choice(["1", "2", "3"]), default="1")
    answers["preference"] = pref_choices[pref_choice][0]

    console.print()
    console.print("[dim]导航员正在为你制定计划...[/dim]")
    console.print()

    with console.status("[cyan]导航员正在思考...[/cyan]"):
        result = voyage.create_plan(answers)

    if not result["success"]:
        console.print(f"[red]{result['error']}[/red]")
        return

    plan = result["plan"]

    console.print(f"[bold green]✓ 计划已生成：{plan['name']} · {plan['total_days']} 天[/bold green]")
    if answers.get("start_weight_kg") and answers.get("target_weight_kg"):
        console.print(
            f"  {answers['start_weight_kg']}kg → {answers['target_weight_kg']}kg"
        )

    console.print()
    console.print("[bold]阶段预览：[/bold]")
    for stage in plan.get("stages", []):
        start, end = stage["days"]
        console.print(f"  [cyan]{stage['name']:　<8s}[/cyan] 第 {start:>3d}-{end:<3d}天 ·  {stage['daily_task']}")

    if plan.get("milestones"):
        milestone_count = len(plan["milestones"])
        console.print()
        console.print(f"[dim]里程碑：每 {plan['total_days'] // milestone_count} 天一个，共 {milestone_count} 个[/dim]")

    console.print()
    save_it = click.confirm(
        f"保存到 ~/.bestman/plan.yaml 并替换当前计划？",
        default=True,
    )
    if save_it:
        save_plan(plan)
        console.print("[green]✓ 计划已保存[/green]")
    else:
        console.print("[dim]已取消保存。[/dim]")

    console.print()


@plan.command("show")
def plan_show():
    """查看当前健身计划。"""
    _require_init()

    plan = load_plan()
    if plan is None:
        console.print()
        console.print("[dim]尚未制定计划。[/dim]")
        console.print("[dim]运行 [bold green]bestman plan create[/bold green] 来制定你的健身计划。[/dim]")
        console.print()
        return

    render_plan_show(console, plan)


@plan.command("edit")
def plan_edit():
    """用默认编辑器编辑计划文件。

    打开 $EDITOR（默认 vim/vi）编辑 ~/.bestman/plan.yaml。
    """
    _require_init()

    import os
    import subprocess

    plan_path_str = str(BESTMAN_HOME / "plan.yaml")

    if not (BESTMAN_HOME / "plan.yaml").exists():
        console.print("[dim]尚未制定计划，正在创建空模板...[/dim]")
        save_plan({
            "name": "新计划",
            "goal_type": "weight_loss",
            "start_date": "",
            "target_date": "",
            "total_days": 120,
            "profile": {
                "height_cm": None,
                "start_weight_kg": None,
                "target_weight_kg": None,
                "fitness_level": "beginner",
                "preference": "bodyweight",
            },
            "stages": [],
            "milestones": {},
        })

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
    console.print(f"[dim]正在用 {editor} 打开计划文件...[/dim]")
    subprocess.call([editor, plan_path_str])
    console.print()
    console.print("[green]✓ 计划文件已保存。运行 [bold]bestman plan show[/bold] 查看。[/green]")
    console.print()


@main.command()
def skip():
    """使用跳过令牌，休息一天但不中断连击。

    消耗一枚跳过令牌来记录今天的训练（不推进地图）。
    连续打卡 7 天可获得一枚跳过令牌。
    """
    _require_init()

    from bestman.core.voyage import Voyage
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

    # 船员对话
    crew_msg = result.get("crew_dialogue")
    if crew_msg:
        console.print(f"[bold cyan][{crew_msg['name']}][/bold cyan] {crew_msg['text']}")
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

    from bestman.core.voyage import Voyage
    voyage = Voyage()

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

    from bestman.core.voyage import Voyage
    from rich.rule import Rule

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

    from bestman.core.voyage import Voyage
    from rich.rule import Rule

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
            handle_plan_override(console, voyage, result)
        else:
            console.print(f"[yellow]{result['response']}[/yellow]")
        return

    # 对话循环模式
    console.print()
    console.print(Rule("[bold cyan]与导航员对话[/bold cyan]"))
    console.print()
    console.print("[dim]输入 [bold]quit[/bold]/[bold]exit[/bold]/[bold]back[/bold] 结束对话[/dim]")
    console.print()

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
            handle_plan_override(console, voyage, result)
        else:
            console.print(f"[yellow]{result['response']}[/yellow]")
        console.print()


@main.command()
def review():
    """查看本周航行回顾。

    聚合本周的打卡、航行距离、金币数据，导航员给出一句总结。
    """
    _require_init()

    from bestman.core.voyage import Voyage
    voyage = Voyage()
    with console.status("[cyan]导航员正在总结本周航行...[/cyan]"):
        result = voyage.review()

    render_review(console, result)


@main.command()
@click.argument("weight", type=float)
@click.option("-d", "--date", "date_str", default=None, help="指定日期 YYYY-MM-DD")
@click.option("-n", "--note", default="", help="备注")
def weigh(weight, date_str, note):
    """记录体重。

    \b
    示例：
        bestman weigh 128.5           # 记录今日体重
        bestman weigh 128.5 -n "空腹"  # 带备注
    """
    _require_init()

    from bestman.core.voyage import Voyage
    voyage = Voyage()

    if not voyage.llm.available:
        result = voyage.record_weight(weight, date_str=date_str, note=note)
    else:
        with console.status("[cyan]导航员正在分析体重趋势...[/cyan]"):
            result = voyage.record_weight(weight, date_str=date_str, note=note)

    console.print()
    current = result["current_weight"]
    if result["distance_to_target"] is not None:
        target_str = f"，距目标 {result['distance_to_target']:.1f} kg"
    else:
        target_str = ""

    if result["delta"] is not None:
        delta = result["delta"]
        arrow = "↓" if delta < 0 else ("↑" if delta > 0 else "→")
        delta_str = f"距上次 {arrow} {abs(delta):.1f} kg"
    else:
        delta_str = "首次记录"

    console.print(f"⚖  [bold cyan]{current} kg[/bold cyan]（{delta_str}{target_str}）")
    console.print(f"[cyan]导航员：{result['comment']}[/cyan]")
    console.print()


@main.command()
def progress():
    """查看体重趋势。

    显示最近 4 周的体重变化趋势和预计达标日期。
    """
    _require_init()

    from bestman.core.voyage import Voyage
    voyage = Voyage()
    result = voyage.get_weight_progress()

    render_progress(console, result)


# ── vessel 载具管理 ──────────────────────────────────────────────

@main.group()
def vessel():
    """载具管理。

    查看和切换当前主题下的可用载具。
    不同载具有不同的像素精灵外观，部分载具需要金币购买。

    \b
    示例：
        bestman vessel list        # 列出可用载具
        bestman vessel set dragon  # 切换到龙头战船
    """
    _require_init()


@vessel.command("list")
def vessel_list():
    """列出当前主题下的所有载具。

    显示载具名称、图标、价格和是否已拥有。
    """
    from bestman.core.voyage import Voyage
    voyage = Voyage()
    theme = voyage.theme
    current_vessel = voyage.current_vessel
    owned = set(voyage.config.get("profile", {}).get("vessel_owned", ["schooner"]))

    render_vessel_list(console, theme, current_vessel, owned)


@vessel.command("set")
@click.argument("name")
def vessel_set(name):
    """切换当前载具。

    \b
    示例：
        bestman vessel set dragon   # 切换到龙头战船
        bestman vessel set schooner # 切回初阶帆船
    """
    from bestman.core.voyage import Voyage
    voyage = Voyage()
    theme = voyage.theme

    if name not in theme.vessels:
        available = ", ".join(theme.vessels.keys())
        console.print(f"[red]未知载具：{name}[/red]")
        console.print(f"[dim]可用载具：{available}[/dim]")
        return

    owned = set(voyage.config.get("profile", {}).get("vessel_owned", ["schooner"]))
    if name not in owned:
        vdef = theme.vessels[name]
        console.print(f"[yellow]你尚未拥有 {vdef.icon} {vdef.name}。[/yellow]")
        console.print(f"[dim]需要 {vdef.price} 金币购买。[/dim]")
        return

    cfg = load_config()
    cfg.setdefault("profile", {})["vessel"] = name
    save_config(cfg)

    vdef = theme.vessels[name]
    console.print(f"[green]✓ 载具已切换为 {vdef.icon} {vdef.name}[/green]")
    console.print("[dim]运行 [bold green]bestman[/bold green] 查看仪表盘。[/dim]")
    console.print()


# ── crew 船员管理 ────────────────────────────────────────────────

@main.group(invoke_without_command=True)
@click.pass_context
def crew(ctx):
    """船员管理。

    查看、招募、解雇船员，与船员对话互动。

    \b
    示例：
        bestman crew                  # 查看船员列表
        bestman crew hire captain     # 招募船长
        bestman crew hire random      # 随机招募
        bestman crew talk doctor      # 与船医对话
        bestman crew gift cook        # 赠送礼物
    """
    if ctx.invoked_subcommand is None:
        _require_init()
        crew_list.callback()


@crew.command("list")
def crew_list():
    """查看所有船员状态。

    显示在船船员的名字、角色、等级、情绪和技能冷却状态。
    """
    from bestman.core.voyage import Voyage
    voyage = Voyage()
    status = voyage.crew_manager.get_crew_status()

    console.print()
    if not status["crew"]:
        console.print("[dim]船上还没有船员。[/dim]")
        console.print(f"[dim]运行 [bold green]bestman crew hire <角色>[/bold green] 招募第一位船员。[/dim]")
        console.print(f"[dim]可招募角色：captain, doctor, lookout, bosun, cook[/dim]")
        console.print()
        return

    console.print("[bold cyan]╔════════════════════════════╗[/bold cyan]")
    console.print(f"[bold cyan]║  船员列表 ({len(status['crew'])}/{status['max_slots']})[/bold cyan]")

    for c in status["crew"]:
        marker = "[bold yellow]★[/bold yellow]" if c["is_main"] else " ○"
        name_str = f"[bold cyan]{c['name']}[/bold cyan]"
        rarity_color = {"common": "white", "rare": "blue", "legendary": "yellow"}.get(c["rarity"], "white")
        rarity_str = f"[{rarity_color}]{c['rarity']}[/{rarity_color}]"
        mood_icon = c["mood_description"]

        skill = c.get("special_skill", {})
        cooldown_str = ""
        if c.get("skill_cooldown_until"):
            cooldown_str = " [dim](技能冷却中)[/dim]"

        console.print(
            f"[bold cyan]║[/bold cyan] {marker} {name_str} Lv.{c['level']} {rarity_str}  {mood_icon}{cooldown_str}"
        )

    console.print("[bold cyan]╚════════════════════════════╝[/bold cyan]")
    console.print()

    # 任务
    if status["quests"]:
        console.print("[bold]本周任务：[/bold]")
        for q in status["quests"]:
            if q["completed"]:
                bar = "[green]✓ 已完成[/green]"
            else:
                bar = f"[{'█' * q['progress']}{'░' * (q['target'] - q['progress'])}] {q['progress']}/{q['target']}"
            console.print(f"  [cyan]{q['crew_name']}[/cyan]: {q['quest_type']} {bar}")

    console.print()
    console.print(f"[dim]船员上限：{status['max_slots']} 人 · 金币：{voyage.state.get_total_coins()} 💰[/dim]")
    console.print(f"[dim]命令：[bold green]bestman crew hire[/bold green] | [bold green]talk[/bold green] | [bold green]upgrade[/bold green] | [bold green]gift[/bold green][/dim]")
    console.print()


@crew.command("hire")
@click.argument("role", required=True)
def crew_hire(role):
    """招募船员。

    \b
    指定角色名进行定向招募，或使用 random 进行随机招募。
    随机招募每日首次半价（50 金币）。

    \b
    示例：
        bestman crew hire captain    # 定向招募船长（500 金币）
        bestman crew hire random     # 随机招募（100 金币 / 首次 50）
    """
    from bestman.core.voyage import Voyage
    voyage = Voyage()
    cm = voyage.crew_manager

    if role.lower() == "random":
        result = cm.random_hire()
        if result["success"]:
            c = result["crew"]
            rarity_color = {"common": "white", "rare": "cyan", "legendary": "yellow"}.get(c["rarity"], "white")
            console.print(f"[green]✓ 招募成功！[/green]")
            console.print(f"  获得 [{rarity_color}]{c['rarity']}[/{rarity_color}] 船员：[bold cyan]{c['name']}[/bold cyan]")
            console.print(f"  花费：[yellow]{result['coins_spent']}[/yellow] 金币")
            console.print(f"[dim]运行 [bold green]bestman crew[/bold green] 查看船员列表。[/dim]")
        else:
            console.print(f"[yellow]{result['error']}[/yellow]")
            if result["rarity"]:
                console.print(f"[dim]抽中稀有度：{result['rarity']}[/dim]")
    else:
        result = cm.hire(role.lower())
        if result["success"]:
            c = result["crew"]
            console.print(f"[green]✓ 招募成功！[/green]")
            console.print(f"  [bold cyan]{c['name']}[/bold cyan] 已登船！")
            console.print(f"  花费：[yellow]{result['coins_spent']}[/yellow] 金币")
            # 显示角色简介
            char = cm.get_character(role.lower())
            if char:
                console.print(f"  [dim]{char.get('backstory', '')}[/dim]")
        else:
            console.print(f"[yellow]{result['error']}[/yellow]")

    console.print()


@crew.command("fire")
@click.argument("role_id")
def crew_fire(role_id):
    """解雇船员。

    解雇后可获得 50% 金币退款（传奇角色 60%）。
    被解雇的船员可花费原价 80% 召回。

    \b
    示例：
        bestman crew fire captain   # 解雇船长
    """
    from bestman.core.voyage import Voyage
    voyage = Voyage()
    cm = voyage.crew_manager

    # 通过 role_id 找到 crew_id
    active = voyage.state.list_crew(active_only=True)
    target = next((c for c in active if c["role_id"] == role_id.lower()), None)
    if target is None:
        console.print(f"[yellow]船上没有角色：{role_id}[/yellow]")
        console.print(f"[dim]运行 [bold green]bestman crew[/bold green] 查看当前船员。[/dim]")
        return

    char = cm.get_character(target["role_id"])
    name = char["name"] if char else target["name"]

    confirm = click.confirm(f"确认解雇 [bold cyan]{name}[/bold cyan]？将退还部分金币。", default=False)
    if not confirm:
        console.print("[dim]已取消。[/dim]")
        return

    result = cm.fire(target["id"])
    if result["success"]:
        console.print(f"[green]✓ {name} 已离船。[/green]")
        console.print(f"  退款：[yellow]{result['refund']}[/yellow] 金币")
    else:
        console.print(f"[yellow]{result['error']}[/yellow]")

    console.print()


@crew.command("talk")
@click.argument("role_id")
def crew_talk(role_id):
    """与船员对话。

    手动触发船员说一段话。
    每天第一次免费，后续每次 50 金币。

    \b
    示例：
        bestman crew talk cook     # 与厨师聊天
    """
    from bestman.core.voyage import Voyage
    from datetime import date
    voyage = Voyage()
    cm = voyage.crew_manager
    today = date.today().isoformat()

    active = voyage.state.list_crew(active_only=True)
    target = next((c for c in active if c["role_id"] == role_id.lower()), None)
    if target is None:
        console.print(f"[yellow]船上没有角色：{role_id}[/yellow]")
        return

    # 检查今日免费次数
    today_count = voyage.state.get_crew_dialogue_count_today(target["id"], today)
    free_talks = cm.crew_config.get("daily_free_talk", 1)
    is_free = today_count < free_talks

    if not is_free:
        cost = cm.crew_config.get("emergency_talk_cost", 50)
        total_coins = voyage.state.get_total_coins()
        if total_coins < cost:
            console.print(f"[yellow]金币不足（需要 {cost}，当前 {total_coins}）[/yellow]")
            return
        cm._spend_coins(cost, today)
        console.print(f"[dim]（花费 {cost} 金币）[/dim]")

    result = cm.manual_talk(target["id"])
    if result["success"]:
        char = cm.get_character(target["role_id"])
        name = char["name"] if char else target["name"]
        console.print(f"[bold cyan][{name}][/bold cyan] {result['text']}")
    else:
        console.print(f"[yellow]{result['error']}[/yellow]")

    console.print()


@crew.command("info")
@click.argument("role_id")
def crew_info(role_id):
    """查看船员详细信息。

    显示角色背景、技能、本周任务、情绪和对话历史。

    \b
    示例：
        bestman crew info doctor   # 查看船医详情
    """
    from bestman.core.voyage import Voyage
    voyage = Voyage()
    cm = voyage.crew_manager

    active = voyage.state.list_crew(active_only=True)
    target = next((c for c in active if c["role_id"] == role_id.lower()), None)
    if target is None:
        console.print(f"[yellow]船上没有角色：{role_id}[/yellow]")
        return

    char = cm.get_character(target["role_id"])
    if char is None:
        console.print(f"[red]角色配置缺失[/red]")
        return

    console.print()
    console.print(f"[bold cyan]╔══ {char['name']} ══╗[/bold cyan]")
    console.print(f"[bold cyan]║[/bold cyan] 角色：[cyan]{target['role_id']}[/cyan]")
    console.print(f"[bold cyan]║[/bold cyan] 稀有度：[{target['rarity']}]{target['rarity']}[/{target['rarity']}]")
    console.print(f"[bold cyan]║[/bold cyan] 等级：Lv.{target['level']} (XP: {target['xp']})")
    console.print(f"[bold cyan]║[/bold cyan] 情绪：{cm._mood_description(target['mood'])} ({target['mood']}/100)")
    console.print(f"[bold cyan]║[/bold cyan] 性格：[dim]{char.get('personality', '')}[/dim]")
    console.print(f"[bold cyan]║[/bold cyan] 专长：[dim]{', '.join(char.get('specialties', []))}[/dim]")
    console.print(f"[bold cyan]╟── 背景 ──[/bold cyan]")
    console.print(f"[bold cyan]║[/bold cyan] [dim]{char.get('backstory', '')}[/dim]")

    skill = char.get("special_skill", {})
    if skill:
        cooldown_str = f"冷却 {skill.get('cooldown_days', 0)} 天" if skill.get("cooldown_days") else "无冷却"
        console.print(f"[bold cyan]╟── 技能 ──[/bold cyan]")
        console.print(f"[bold cyan]║[/bold cyan] [bold]{skill.get('name', '')}[/bold]: {skill.get('description', '')}")
        console.print(f"[bold cyan]║[/bold cyan] {cooldown_str}")

    # 任务
    quests = voyage.state.get_crew_quests(target["id"], limit=3)
    if quests:
        console.print(f"[bold cyan]╟── 近期任务 ──[/bold cyan]")
        for q in quests:
            status_str = "[green]✓[/green]" if q["completed"] else f"{q['progress']}/{q['target']}"
            console.print(f"[bold cyan]║[/bold cyan] {q['week_start_date']} {q['quest_type']} {status_str}")

    console.print(f"[bold cyan]╚{'═' * 20}╝[/bold cyan]")
    console.print()

    # 最近对话
    dialogues = voyage.state.get_crew_dialogues(target["id"], limit=5)
    if dialogues:
        console.print(f"[dim]最近对话：[/dim]")
        for d in dialogues:
            console.print(f"  [dim]{d['date']}[/dim] [{d['trigger_type']}] {d['text']}")
        console.print()


@crew.command("upgrade")
@click.argument("role_id")
def crew_upgrade(role_id):
    """升级船员。

    使用金币提升船员等级，每级费用递增。
    升级解锁新对话和增强技能效果。

    \b
    示例：
        bestman crew upgrade cook
    """
    from bestman.core.voyage import Voyage
    voyage = Voyage()
    cm = voyage.crew_manager

    active = voyage.state.list_crew(active_only=True)
    target = next((c for c in active if c["role_id"] == role_id.lower()), None)
    if target is None:
        console.print(f"[yellow]船上没有角色：{role_id}[/yellow]")
        return

    char = cm.get_character(target["role_id"])
    name = char["name"] if char else target["name"]

    if target["level"] >= cm.crew_config.get("max_level", 10):
        console.print(f"[yellow]{name} 已达到最高等级。[/yellow]")
        return

    base_cost = cm.crew_config.get("upgrade_base_cost", 100)
    increment = cm.crew_config.get("upgrade_cost_increment", 20)
    cost = base_cost + (target["level"] - 1) * increment

    console.print(f"升级 [bold cyan]{name}[/bold cyan] Lv.{target['level']} → Lv.{target['level']+1}")
    console.print(f"费用：[yellow]{cost}[/yellow] 金币")
    confirm = click.confirm("确认升级？", default=True)
    if not confirm:
        console.print("[dim]已取消。[/dim]")
        return

    result = cm.upgrade(target["id"])
    if result["success"]:
        console.print(f"[green]✓ {name} 升至 Lv.{result['new_level']}！[/green]")
        console.print(f"  花费：[yellow]{result['coins_spent']}[/yellow] 金币")
    else:
        console.print(f"[yellow]{result['error']}[/yellow]")

    console.print()


@crew.command("gift")
@click.argument("role_id")
def crew_gift(role_id):
    """赠送礼物给船员。

    花费 30 金币提升船员情绪 20 点。

    \b
    示例：
        bestman crew gift cook    # 给厨师送礼物
    """
    from bestman.core.voyage import Voyage
    from datetime import date
    voyage = Voyage()
    cm = voyage.crew_manager

    active = voyage.state.list_crew(active_only=True)
    target = next((c for c in active if c["role_id"] == role_id.lower()), None)
    if target is None:
        console.print(f"[yellow]船上没有角色：{role_id}[/yellow]")
        return

    char = cm.get_character(target["role_id"])
    name = char["name"] if char else target["name"]

    cost = cm.crew_config.get("gift_cost", 30)
    total_coins = voyage.state.get_total_coins()
    if total_coins < cost:
        console.print(f"[yellow]金币不足（需要 {cost}，当前 {total_coins}）[/yellow]")
        return

    confirm = click.confirm(f"花费 [yellow]{cost}[/yellow] 金币给 [bold cyan]{name}[/bold cyan] 送礼物？", default=True)
    if not confirm:
        console.print("[dim]已取消。[/dim]")
        return

    cm._spend_coins(cost, date.today().isoformat())
    new_mood = cm.boost_mood(target["id"], cm.crew_config.get("gift_mood_boost", 20))

    console.print(f"[green]✓ 已送出礼物！[/green]")
    console.print(f"  {name} 的情绪：{cm._mood_description(target['mood'])} → {cm._mood_description(new_mood)}")
    console.print(f"[dim]（{name} 看起来很开心）[/dim]")
    console.print()


@crew.command("quest")
def crew_quest():
    """查看船员任务。

    显示所有船员的本周任务及完成进度。
    """
    from bestman.core.voyage import Voyage
    voyage = Voyage()
    cm = voyage.crew_manager

    quests = voyage.state.get_active_quests()

    console.print()
    if not quests:
        console.print("[dim]暂无活跃任务。完成任务后会自动生成下周任务。[/dim]")
        console.print()
        return

    console.print("[bold cyan]═ 本周船员任务 ═[/bold cyan]")
    console.print()
    for q in quests:
        status_icon = "[green]✓[/green]" if q["completed"] else "[yellow]○[/yellow]"
        reward_str = ""
        if q["completed"] and not q["reward_claimed"]:
            reward_str = " [yellow dim]（奖励待领取）[/yellow dim]"
        elif q["completed"] and q["reward_claimed"]:
            reward_str = " [dim]（已领取）[/dim]"

        progress_bar = f"[{'█' * q['progress']}{'░' * (q['target'] - q['progress'])}] {q['progress']}/{q['target']}"
        console.print(f"  {status_icon} [cyan]{q['crew_name']}[/cyan]: {q['quest_type']} {progress_bar}{reward_str}")

    console.print()
    console.print("[dim]任务自动推进——完成打卡、发现宝藏等行为会累积进度。[/dim]")
    console.print()


@crew.command("set-main")
@click.argument("role_id")
def crew_set_main(role_id):
    """设置主船员。

    主船员在打卡后优先发言。

    \b
    示例：
        bestman crew set-main captain
    """
    from bestman.core.voyage import Voyage
    voyage = Voyage()

    active = voyage.state.list_crew(active_only=True)
    target = next((c for c in active if c["role_id"] == role_id.lower()), None)
    if target is None:
        console.print(f"[yellow]船上没有角色：{role_id}[/yellow]")
        return

    if target["is_main"]:
        console.print(f"[dim]{target['name']} 已经是主船员。[/dim]")
        return

    voyage.state.set_main_crew(target["id"])
    console.print(f"[green]✓ {target['name']} 已设为主船员 ★[/green]")
    console.print()


@crew.command("shop")
def crew_shop():
    """船员商店。

    浏览可招募的船员角色及价格。
    """
    from bestman.core.voyage import Voyage
    voyage = Voyage()
    cm = voyage.crew_manager

    active_roles = {c["role_id"] for c in voyage.state.list_crew(active_only=True)}
    total_coins = voyage.state.get_total_coins()

    console.print()
    console.print("[bold cyan]══ 船员商店 ══[/bold cyan]")
    console.print(f"[dim]金币余额：[yellow]{total_coins}[/yellow] 💰[/dim]")
    console.print()

    for rid, char in cm.characters.items():
        owned = rid in active_roles
        rarity = char.get("rarity", "common")
        rarity_color = {"common": "white", "rare": "cyan", "legendary": "yellow"}.get(rarity, "white")
        cost = char.get("hire_cost", 500)
        can_afford = total_coins >= cost

        if owned:
            status = "[dim]（已拥有）[/dim]"
        elif can_afford:
            status = f"[yellow]{cost} 金币[/yellow] [green]可购买[/green]"
        else:
            status = f"[yellow]{cost} 金币[/yellow] [red]金币不足[/red]"

        console.print(f"  [{rarity_color}]{rarity:　<4s}[/{rarity_color}] [bold cyan]{char['name']:　<4s}[/bold cyan] {status}")
        console.print(f"         [dim]{char.get('specialties', [])[0] if char.get('specialties') else ''} · {char.get('personality', '')}[/dim]")

    console.print()
    console.print("[dim]招募命令：[/dim]")
    console.print("[dim]  [bold green]bestman crew hire <角色ID>[/bold green]  — 定向招募[/dim]")
    console.print("[dim]  [bold green]bestman crew hire random[/bold green]    — 随机招募（100金币，每日首抽50）[/dim]")
    console.print()


# Register the `map` subcommand separately to avoid name collision with
# the built-in ``map`` function.
main.add_command(map_cmd, name="map")
