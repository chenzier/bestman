"""CLI 视图函数 — Rich 输出逻辑。

从 cli.py 中提取的纯渲染函数，薄层 Click 命令调用它们来输出结果。
每个函数接收 console 和业务数据，产出终端输出。
"""

import math
import sys
import time
from datetime import date, timedelta

from rich.panel import Panel
from rich.rule import Rule

from bestman.config import load_plan, save_plan
from bestman.renderers.canvas import kitty_available, kitty_display as canvas_kitty_display, CanvasRenderer


# ── 仪表盘 ──────────────────────────────────────────────────────

def render_dashboard(console, voyage):
    """渲染仪表盘（默认命令）。

    显示地图、状态行、今日任务、最近日志和命令提示。
    地图优先使用 Canvas PNG，不可用时回退 ASCII Rich。
    """
    from bestman.renderers.canvas import CanvasRenderer

    status = voyage.get_status()

    # Rule 头
    console.print(Rule("[bold cyan]bestman — 航向新大陆[/bold cyan]"))
    console.print()

    # 地图：优先 Canvas，回退 Rich
    _render_map_or_canvas(console, voyage)
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

    # 进度条
    progress = status["current_day"] / status["total_days"]
    bar_w = 30
    filled = int(bar_w * progress)
    bar = f"[bold cyan]{'█' * filled}[/][dim]{'░' * (bar_w - filled)}[/]"
    console.print(f"进度 {bar} {int(progress*100)}%")

    # 图例
    console.print(
        "图例:  [bold cyan]◉[/]起点  [bold yellow]⚓[/]船  [bold magenta]✦[/]里程碑  "
        "[dim blue]▒[/]迷雾"
    )
    console.print()

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


# ── 打卡结果 ────────────────────────────────────────────────────

def _render_map_or_canvas(console, voyage, **kw):
    """Render the map: Canvas PNG if available, else ASCII Rich markup."""
    status = voyage.get_status()
    if kitty_available():
        try:
            canvas_renderer = CanvasRenderer()
            png = canvas_renderer.render_map(
                data=voyage.map_engine.build_render_data(
                    tiles_revealed=status["tiles_revealed"],
                    **kw,
                ),
                theme=voyage.theme,
                vessel_def=voyage.theme.vessels.get(voyage.current_vessel),
            )
            canvas_kitty_display(png, cols=120, rows=24)
            return
        except Exception:
            pass
    console.print(voyage.render_map(**kw))


def render_done(console, voyage, result, total_advance, mode="deterministic"):
    """渲染打卡完成后的结果。

    显示地图、日志、金币、宝藏、里程碑、事件。
    如果启用了摇晃动画，播放摇摆效果。
    """
    tiles = result["tiles_revealed"]
    status = voyage.get_status()
    total = status["total_days"]
    region = status.get("region", status["stage"]["name"])
    rule_text = f"⚓ 第 {tiles} 天 · {region}"

    # 摇摆动画
    sway_config = voyage.config.get("today_trail", {}).get("sway", {})
    do_sway = sway_config.get("enabled", True) and total_advance > 0

    if do_sway:
        amplitude = sway_config.get("amplitude", 2)
        fps = sway_config.get("fps", 8)
        sway_duration = sway_config.get("duration", 0.6)
        total_frames = max(1, int(fps * sway_duration))
        map_lines = voyage.map_engine.height + 1

        # First frame — ASCII for fast line-by-line redraw
        console.print(Rule(rule_text, style="dim cyan"))
        console.print(voyage.render_map(
            today_advance=total_advance,
            sway_offset=amplitude, sway_phase=0))
        time.sleep(0.3)

        for frame in range(1, total_frames):
            progress = frame / total_frames
            current_offset = amplitude * (1.0 - progress)
            phase = frame * (4 * math.pi / total_frames)

            sys.stdout.write(f"\033[{map_lines}A\033[J")
            sys.stdout.flush()
            console.print(Rule(rule_text, style="dim cyan"))
            console.print(voyage.render_map(
                today_advance=total_advance,
                sway_offset=current_offset, sway_phase=phase))
            time.sleep(1.0 / fps)

        # Replace animation area with clear space, then show Canvas PNG
        sys.stdout.write(f"\033[{map_lines}A\033[J")
        sys.stdout.flush()

    # Final static map — Canvas PNG if available
    console.print(Rule(rule_text, style="dim cyan"))
    _render_map_or_canvas(console, voyage, today_advance=total_advance)
    console.print()

    # 今日航程数字确认
    if total_advance > 0:
        console.print(f"[bold cyan]📍 今日航程: +{total_advance} 海里[/bold cyan]")
    console.print()

    if result.get("llm_used"):
        console.print("[dim]（日志由 AI 导航员生成）[/dim]")
    console.print()

    # 日志
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


# ── 地图概览 ────────────────────────────────────────────────────

def render_map_view(console, voyage):
    """渲染航行地图概览：全部阶段、里程碑与进度。"""
    status = voyage.get_status()
    tiles = status["tiles_revealed"]
    current_day = status["current_day"]

    console.print()
    console.print("[bold cyan]⚓ 航行地图 — 175 天航向新大陆[/bold cyan]")
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

        bar_width = 15
        filled = int(bar_width * completed_in_stage / stage_length) if stage_length > 0 else 0
        empty = bar_width - filled
        bar = f"[{bar_color}]" + "█" * filled + "░" * empty + "[/]"

        milestone_name = milestones.get(end)
        milestone_text = f"[dim]✦ 里程碑：DAY {end} · {milestone_name}[/dim]" if milestone_name else ""

        console.print(f"  {icon} [{name_style}]{name}[/{name_style}]  DAY {start}-{end}  [{bar}] {completed_in_stage}/{stage_length}")
        if milestone_text:
            console.print(f"    {milestone_text}")

    console.print()
    console.print("[dim]地图源自 bestman init 时配置的航程。[/dim]")
    console.print()


# ── 计划展示 ────────────────────────────────────────────────────

def render_plan_show(console, plan):
    """渲染计划展示。"""
    console.print()
    console.print(Rule(f"[bold cyan]{plan.get('name', '健身计划')}[/bold cyan]"))
    console.print()

    goal_type_labels = {
        "weight_loss": "减肥",
        "muscle_gain": "增肌",
        "habit": "养成运动习惯",
        "custom": "自定义",
    }
    goal_type = goal_type_labels.get(plan.get("goal_type", ""), plan.get("goal_type", ""))

    console.print(f"目标：[cyan]{goal_type}[/cyan]")
    console.print(f"周期：[cyan]{plan.get('start_date', '?')}[/cyan] → [cyan]{plan.get('target_date', '?')}[/cyan]（{plan.get('total_days', '?')} 天）")

    profile = plan.get("profile", {})
    if profile:
        weight_info = ""
        if profile.get("start_weight_kg") and profile.get("target_weight_kg"):
            weight_info = f" · {profile['start_weight_kg']}kg → {profile['target_weight_kg']}kg"
        elif profile.get("start_weight_kg"):
            weight_info = f" · {profile['start_weight_kg']}kg"
        console.print(f"身体数据：{profile.get('height_cm', '?')}cm{weight_info}")

        fitness_labels = {"beginner": "几乎不运动", "occasional": "偶尔运动", "intermediate": "有一定基础"}
        pref_labels = {"bodyweight": "居家自重", "outdoor": "户外", "mixed": "混合"}
        console.print(
            f"基础：[cyan]{fitness_labels.get(profile.get('fitness_level', ''), profile.get('fitness_level', ''))}[/cyan]"
            f" · 偏好：[cyan]{pref_labels.get(profile.get('preference', ''), profile.get('preference', ''))}[/cyan]"
        )

    console.print()

    console.print("[bold]阶段安排：[/bold]")
    for stage in plan.get("stages", []):
        start, end = stage["days"]
        console.print(f"  [cyan]{stage['name']:　<8s}[/cyan] 第 {start:>3d}-{end:<3d}天 ·  {stage['daily_task']}")

    milestones = plan.get("milestones", {})
    if milestones:
        console.print()
        console.print("[bold]里程碑：[/bold]")
        for d, name in sorted(milestones.items(), key=lambda x: int(x[0])):
            console.print(f"  DAY {d:>3d} · [dim]{name}[/dim]")

    console.print()


# ── 载具列表 ───────────────────────────────────────────────────

def render_vessel_list(console, theme, current_vessel, owned):
    """渲染载具列表。"""
    console.print()
    console.print(Rule(f"[bold cyan]{theme.name} 主题 · 载具[/bold cyan]"))
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
    console.print("[dim]切换载具：[bold green]bestman vessel set <名称>[/bold green][/dim]")
    console.print()


# ── 回顾 ────────────────────────────────────────────────────────

def render_review(console, result):
    """渲染每周回顾。"""
    console.print()
    console.print(
        f"══════════ 第 {result['week_number']} 周回顾 ═══════════"
    )
    console.print(
        f"打卡：[bold green]{result['check_ins']}/{result['days_in_week']}[/bold green]"
        f" {'✓' if result['check_ins'] == result['days_in_week'] else ''}"
        f"  跳过：{result['skips']}  连击：[bold yellow]{result['streak']} 天[/bold yellow]"
    )
    console.print(
        f"总航行：[bold cyan]{result['total_tiles']} 海里[/bold cyan]"
        f"（均 [bold cyan]{result['avg_tiles']:.1f}[/bold cyan]/天）"
    )
    console.print(
        f"最远：[bold yellow]{result['max_tiles']} 海里[/bold yellow]"
        f"  最短：{result['min_tiles']} 海里"
    )
    console.print(f"金币：[bold yellow]+{result['coins']}[/bold yellow]")

    if result["summary"]:
        console.print()
        console.print(f"[cyan]导航员：{result['summary']}[/cyan]")

    console.print()


# ── 趋势 ────────────────────────────────────────────────────────

def render_progress(console, result):
    """渲染体重趋势。"""
    console.print()
    console.print("══════════ 趋势 ═══════════")

    entries = result["entries"]
    if not entries:
        console.print()
        console.print("[dim]尚无体重记录。运行 [bold green]bestman weigh <体重>[/bold green] 开始记录。[/dim]")
        console.print()
        return

    if entries:
        weights = [e["weight_kg"] for e in entries]
        max_w = max(weights)
        min_w = min(weights) if len(weights) > 1 else max_w - 5
        weight_range = max(max_w - min_w, 5)

        console.print("体重（最近 4 次）：")
        for e in entries:
            w = e["weight_kg"]
            bar_fill = int(20 * (w - min_w) / weight_range) if weight_range > 0 else 10
            bar_fill = max(1, min(bar_fill, 20))
            bar = "█" * bar_fill + "░" * (20 - bar_fill)
            console.print(f"  {e['date']}  [bold cyan]{bar}[/bold cyan] {w:.1f}")
        console.print()

    if result["weekly_avg_loss"] is not None:
        avg_loss = result["weekly_avg_loss"]
        arrow = "↓" if avg_loss < 0 else "↑"
        console.print(f"📉 周均 {arrow} {abs(avg_loss):.1f} kg", end="")

        if result["estimated_completion_date"] and result["estimated_completion_date"] != "已达标":
            console.print(f" · 预计达标 [bold yellow]{result['estimated_completion_date']}[/bold yellow]")
        elif result["estimated_completion_date"] == "已达标":
            console.print(" · [bold green]已达标！[/bold green]")
        else:
            console.print()

    console.print()


# ── 计划覆盖处理 ───────────────────────────────────────────────

def handle_plan_override(console, voyage, talk_result):
    """处理 talk 返回的 plan_override。"""
    override = talk_result.get("plan_override")
    if not override:
        return

    field = override.get("field", "daily_task")
    value = override.get("value", "")
    duration_days = override.get("duration_days", 3)

    if not value:
        return

    today = date.today()
    expires = (today + timedelta(days=duration_days)).isoformat()

    # 获取原始值
    original_value = voyage.config["voyage"]["default_daily_task"]
    plan = load_plan()
    if plan:
        stage_info = voyage._get_plan_stage_info()
        if stage_info:
            original_value = stage_info.get("daily_task", original_value)

    voyage.state.add_override(
        created_date=today.isoformat(),
        field=field,
        original_value=original_value,
        override_value=value,
        expires_date=expires,
        reason="导航员根据水手情况临时调整",
    )

    console.print()
    console.print(f"[dim]（计划已更新：{expires} 自动恢复）[/dim]")
