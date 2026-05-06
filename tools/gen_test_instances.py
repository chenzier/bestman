"""Generate test bestman instances with different progress levels.

Usage:
    python tools/gen_test_instances.py [--base ~/.bestman] [--dest /tmp/bestman]
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

# Instance definitions: (name, days_completed, total_days)
INSTANCES = [
    ("bestman20", 20, 175),
    ("bestman50", 50, 175),
    ("bestman80", 80, 175),
    ("bestman120", 120, 175),
    ("bestman150", 150, 175),
]

# Voyage log templates by stage
LOG_POOLS = {
    # 启航 (1-25)
    "启航": [
        ("晨光中升起了主帆，海风带着咸味扑面而来。码头上的人们越来越远，只剩下无尽的海平线。", "narrative"),
        ("船医建议每天做一组平板支撑来对抗晕船。今天的训练在摇晃的甲板上完成了。", "narrative"),
        ("海鸥跟了船一整天。水手长说这是好运的预兆——它们会指引我们找到陆地的方向。", "narrative"),
        ("第一次在海上看到日落。太阳沉入海平面时，天空像被点燃了一样，从橙红渐变到深紫。", "narrative"),
        ("负责夜班瞭望。头顶的星空比陆地上亮十倍，银河像一条发光的河流横贯天际。", "narrative"),
        ("测试了罗盘和六分仪。偏航三度——及时纠正了航线。航海课上学的知识终于派上了用场。", "narrative"),
        ("钓到一条金枪鱼！厨房今晚加餐。厨师说新鲜鱼肉比腌肉有营养得多。", "encouragement"),
        ("今天天气晴朗，海面平静得像一面镜子。水手们称这种天气为'海神的微笑'。训练加倍完成。", "narrative"),
        ("发现一群飞鱼从船头掠过，最远的一只飞了将近50米。大自然的设计真是精妙。", "narrative"),
        ("根据星图，我们已经航行了十天。船长在桅杆上刻下了第一道标记。", "narrative"),
    ],
    # 迷雾之海 (26-50)
    "迷雾之海": [
        ("浓雾笼罩了海面，能见度不到十米。船头悬挂雾钟，每隔一分钟敲响一次。训练在室内完成。", "narrative"),
        ("雾中有奇怪的声音——像是远处的号角。老水手说那是海牛在唱歌，但没人真正确定。", "narrative"),
        ("连续三天大雾。靠罗盘和星历表维持航向。今天的深蹲训练异常认真——需要驱散湿冷。", "narrative"),
        ("雾散了！太阳重新出现的瞬间，整个船爆发出了欢呼。继续全速前进。", "encouragement"),
        ("穿过了一片漂浮的海藻带。导航员说这意味着附近有岛屿。也许明天就能看到陆地。", "narrative"),
        ("发现一艘废弃的渔船，船体上爬满了藤壶。我们没有停留，但这件事被记入了航海日志。", "narrative"),
        ("傍晚雾散时看到了远处的鲸群。至少七头座头鲸在水面上喷水，场面十分壮观。", "narrative"),
        ("根据日志，我们已经航行了三十多天。食物储备充足，士气良好。每日训练完成。", "narrative"),
        ("海流变了方向，船速慢了下来。正好用来做额外的拉伸训练。", "narrative"),
        ("雾中能看到前面有光——那不是灯塔，而是磷光浮游生物在船首激起的蓝色光芒。美得令人屏息。", "narrative"),
    ],
    # 季风带 (51-75)
    "季风带": [
        ("季风如期而至！船帆吃饱了风，速度几乎翻倍。抓紧时间多做了一组训练。", "encouragement"),
        ("风太大了，不得不收起主帆只靠前帆航行。在颠簸的甲板上做俯卧撑是个有趣的挑战。", "narrative"),
        ("导航记录显示我们已经穿过了贸易航线的起点。如果风向保持，很快就能到达下一个里程碑。", "narrative"),
        ("水手在船底发现了几个藤壶附着点。明天需要下水清理——这也算是一种训练吧。", "narrative"),
        ("顺风！今天航行了整整两格。船上的每一个人都精神饱满。", "bonus_tile"),
        ("看到远处的雷暴云，及时调整了航线绕了过去。航海需要耐心和判断力，这和健身很像。", "narrative"),
        ("今天是望日，月亮又大又圆。在月光下完成了今天的训练，有种特别的仪式感。", "narrative"),
        ("遇到了一艘商船，对方用旗语告诉我们前方海域安全，没有海盗。航海者的互助精神令人感动。", "narrative"),
        ("风向稳定，天气晴好。这样的日子最适合在甲板上做户外训练。完成了两组额外的卷腹。", "narrative"),
        ("计算了一下进度：已经完成了总航程的近一半。这是一个值得庆祝的节点。", "encouragement"),
    ],
    # 贸易航线 (76-100)
    "贸易航线": [
        ("进入了繁忙的贸易航线。今天看到了五艘船，其中一艘挂着东方的旗帜。", "narrative"),
        ("在甲板上发现了一只迷路的信天翁。它休息了一小时后继续南飞。我们也该继续训练了。", "narrative"),
        ("和其他船的船长交换了航海图。得知前方有一座小岛可以补充淡水。每日训练照常完成。", "narrative"),
        ("连续多日的航行让身体开始适应海上的节奏。引体向上的数量比出发时增加了不少。", "encouragement"),
        ("路过一个海上贸易站——几艘船锚泊在一起进行海上集市。我们用腌肉换了一些新鲜水果。", "narrative"),
        ("远方隐约能看到一片陆地。虽然只是路过，但看到绿色总是让人心情舒畅。", "narrative"),
        ("海面平静，非常适合测试新的训练动作。参考了船上的健身手册，加入了俄罗斯转体。", "narrative"),
        ("一艘东方商船靠过来，交易了香料和茶叶。航海者们用简单的语言和手势完成了交流。", "narrative"),
        ("今天负责掌舵两个小时。保持航线比看起来难——手臂和肩膀得到了不少锻炼。", "narrative"),
        ("进入热带海域，气温明显升高。调整了训练时间到清晨和傍晚，避开正午的烈日。", "narrative"),
    ],
    # 赤道无风带 (101-125)
    "赤道无风带": [
        ("进入了无风带。海面平得像一块玻璃，一丝风都没有。这是对意志力的真正考验。", "narrative"),
        ("无风第三天。用来整理装备、缝补船帆、加强训练。静止不动不代表没有进步。", "narrative"),
        ("船几乎不动。干脆下海游泳——这也是最好的全身训练。注意周围没有鲨鱼。", "narrative"),
        ("终于在傍晚等来了一阵微风。全船欢呼！继续向南，很快就能进入信风带了。", "encouragement"),
        ("无风带教会了我们耐心。不能控制风，但可以控制自己的训练。今天的任务完成了。", "narrative"),
        ("观测到赤道附近的特殊星象——南十字座第一次出现在天边。这意味着我们已经接近南半球。", "narrative"),
        ("酷热难耐。在甲板上洒水降温，训练量减少但仍然坚持完成。航海不是短跑，是马拉松。", "narrative"),
        ("今天捕获了一只海龟（随后放生了）。据说赤道附近的海龟能带来好运。", "narrative"),
        ("根据导航计算，如果信风如期而至，余下的航程会很顺利。坚持就是胜利。", "encouragement"),
        ("无聊的一天。在海图上研究新大陆的地形图，推算到达日期。", "narrative"),
    ],
    # 信风带 (126-150)
    "信风带": [
        ("信风来了！稳定而强劲的东南风推动着船一路向西南前进。航速达到开航以来最高。", "bonus_tile"),
        ("心情很好。信风带的航行是一种享受——稳定的风，温暖而不炎热，蓝天白云。", "narrative"),
        ("船速快，训练也加倍。水手们在甲板上比赛俯卧撑，输的人要负责擦甲板。", "narrative"),
        ("看到了海豚！一大群海豚在船首伴游，其中一只还跳出水面转了一圈。像是大自然的鼓励。", "encouragement"),
        ("根据海图，我们离新大陆已经不远了。大概再有两三周就能看到海岸线。每个人都很兴奋。", "narrative"),
        ("今天的训练格外认真。想到即将到达的目的地，每个动作都充满了动力。", "encouragement"),
        ("晚上讨论到达新大陆后的计划。有人说要先去酒馆喝一杯，有人说要第一时间写信回家。", "narrative"),
        ("海风带着一丝不同的气息——也许是陆地的味道？可能是错觉，但大家都说闻到了。", "narrative"),
        ("现在每天的训练已经成了习惯。回想启航时的自己，无论是体力还是耐力都有了巨大进步。", "narrative"),
        ("看到远处的云层形状——那种扁平的积云往往意味着下方有陆地。快了，真的快了。", "narrative"),
    ],
    # 新大陆近海 (151-175)
    "新大陆近海": [
        ("看到了！今天早上瞭望员大喊'陆地！'。虽然还只是海平线上的一条绿色细线，但那是真的。", "encouragement"),
        ("海水的颜色变了——从深蓝变成了浅绿，这意味着我们已经在大陆架上。训练照常，心情澎湃。", "narrative"),
        ("陆地越来越近了。能看清海岸线上的树木和山脉。这是从未见过的风景。", "narrative"),
        ("准备靠岸的各种事宜：检查锚链、准备小艇、整理登陆装备。今天的训练完成了最后一组。", "narrative"),
        ("几乎能闻到陆地上的植物味道了。在海上漂泊了一百多天后，这种感觉难以形容。", "narrative"),
        ("最后一次在船上训练。明天就要踏上新大陆的土地了。回顾这一路，每一项训练都值得。", "encouragement"),
        ("也许明天就不再需要训练了。但也许，到达新大陆之后的训练，才代表另一种开始。", "narrative"),
    ],
}

# Test task descriptions
TASKS = [
    "深蹲 3x15",
    "俯卧撑 3x20",
    "平板支撑 2min x3",
    "引体向上 3x10",
    "卷腹 3x25",
    "游泳 30min",
    "瑜伽拉伸 20min",
    "哑铃弯举 3x12",
    "波比跳 3x15",
    "跑步 5km",
    "硬拉 3x10",
]


def get_stage_name(day):
    """Return stage name for a given day number."""
    if day <= 25:
        return "启航"
    elif day <= 50:
        return "迷雾之海"
    elif day <= 75:
        return "季风带"
    elif day <= 100:
        return "贸易航线"
    elif day <= 125:
        return "赤道无风带"
    elif day <= 150:
        return "信风带"
    else:
        return "新大陆近海"


def create_instance(dest_dir, days_completed, total_days, base_dir):
    """Create one test instance with fake progress."""
    dest = Path(dest_dir)
    base = Path(base_dir)

    print(f"Creating {dest_dir} ({days_completed} days)...")

    # 1. Create directory
    dest.mkdir(parents=True, exist_ok=True)

    # 2. Copy config.yaml and plan.yaml from base
    for fname in ["config.yaml", "plan.yaml", ".env"]:
        src = base / fname
        if src.exists():
            shutil.copy2(src, dest / fname)

    # 3. Update config.yaml with correct total_days
    config_path = dest / "config.yaml"
    config = yaml.safe_load(config_path.read_text()) or {}
    config["voyage"]["total_days"] = total_days
    # Update end_date
    today = date.today()
    end_date = today + timedelta(days=total_days - days_completed)
    config["voyage"]["end_date"] = end_date.isoformat()
    config_path.write_text(yaml.dump(config, allow_unicode=True, sort_keys=False))

    # 4. Create SQLite database with fake data
    db_path = dest / "bestman.db"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    # Create schema
    conn.execute("""
        CREATE TABLE IF NOT EXISTS days (
            date TEXT PRIMARY KEY,
            completed INTEGER NOT NULL DEFAULT 0,
            extra INTEGER NOT NULL DEFAULT 0,
            task_done TEXT DEFAULT '',
            used_skip INTEGER NOT NULL DEFAULT 0,
            coins_earned INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voyage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL DEFAULT 'narrative',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skip_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            earned_date TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS treasures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            coins INTEGER NOT NULL,
            discovered_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weights (
            date TEXT PRIMARY KEY,
            weight_kg REAL NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plan_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_date TEXT NOT NULL,
            expires_date TEXT,
            field TEXT NOT NULL,
            original_value TEXT NOT NULL,
            override_value TEXT NOT NULL,
            reason TEXT DEFAULT '',
            active INTEGER DEFAULT 1
        )
    """)

    # 5. Generate day records going backwards from yesterday
    #    (today is NOT recorded so user can do "bestman checkin")
    import random as rng
    rng.seed(hash(dest_dir) % 2**31)

    yesterday = today - timedelta(days=1)
    used_logs_by_stage = {}

    for i in range(days_completed):
        day_date = (yesterday - timedelta(days=days_completed - 1 - i)).isoformat()
        day_num = i + 1

        # Random extra tiles (10% chance of +1)
        extra = 1 if rng.random() < 0.15 else 0

        # Random task
        task = rng.choice(TASKS)

        # Random skip (5% chance)
        used_skip = 1 if rng.random() < 0.05 else 0
        effective_day = 1 if not used_skip else 0

        # Coins: base 10 + extra_tile 5 + random events
        coins = 10 if effective_day else 0
        if extra:
            coins += 5

        conn.execute(
            "INSERT OR REPLACE INTO days (date, completed, extra, task_done, used_skip, coins_earned) VALUES (?, ?, ?, ?, ?, ?)",
            (day_date, effective_day, extra, task, used_skip, coins),
        )

        # Generate voyage log
        stage = get_stage_name(day_num)
        if stage not in used_logs_by_stage:
            used_logs_by_stage[stage] = 0

        pool = LOG_POOLS[stage]
        log_text, log_type = pool[used_logs_by_stage[stage] % len(pool)]
        used_logs_by_stage[stage] += 1

        conn.execute(
            "INSERT INTO voyage_logs (date, text, event_type) VALUES (?, ?, ?)",
            (day_date, log_text, log_type),
        )

    # 6. Add some treasures for more advanced instances
    if days_completed >= 32:
        conn.execute(
            "INSERT INTO treasures (name, type, coins, discovered_date) VALUES (?, ?, ?, ?)",
            ("沉船宝藏", "explicit", 50, (yesterday - timedelta(days=days_completed - 32)).isoformat()),
        )
    if days_completed >= 67:
        conn.execute(
            "INSERT INTO treasures (name, type, coins, discovered_date) VALUES (?, ?, ?, ?)",
            ("海妖巢穴", "explicit", 80, (yesterday - timedelta(days=days_completed - 67)).isoformat()),
        )
    if days_completed >= 110:
        conn.execute(
            "INSERT INTO treasures (name, type, coins, discovered_date) VALUES (?, ?, ?, ?)",
            ("漂流瓶", "explicit", 30, (yesterday - timedelta(days=days_completed - 110)).isoformat()),
        )
    if days_completed >= 145:
        conn.execute(
            "INSERT INTO treasures (name, type, coins, discovered_date) VALUES (?, ?, ?, ?)",
            ("海盗藏宝图", "explicit", 100, (yesterday - timedelta(days=days_completed - 145)).isoformat()),
        )

    # 7. Add skip tokens (milestone rewards: every 30 days)
    tokens_added = 0
    for milestone in [25, 50, 75, 100, 125, 150]:
        if days_completed >= milestone:
            tokens_added += 1
    for _ in range(tokens_added):
        conn.execute(
            "INSERT INTO skip_tokens (earned_date, used) VALUES (?, 0)",
            (yesterday.isoformat(),),
        )

    # 8. Add weight records (every 15 days)
    base_weight = 80.0
    for w in range(1, days_completed + 1, 15):
        weight = base_weight - (w - 1) * 0.3 + rng.uniform(-0.5, 0.5)
        conn.execute(
            "INSERT OR REPLACE INTO weights (date, weight_kg, note) VALUES (?, ?, ?)",
            ((yesterday - timedelta(days=days_completed - w)).isoformat(), round(weight, 1), ""),
        )

    conn.commit()
    conn.close()
    print(f"  Done: {days_completed} days recorded, {days_completed} logs, {tokens_added} skip tokens")


def main():
    parser = argparse.ArgumentParser(description="Generate test bestman instances")
    parser.add_argument("--base", default=str(Path.home() / ".bestman"), help="Base bestman home")
    parser.add_argument("--dest", default=None, help="Destination directory (default: same parent as base)")
    args = parser.parse_args()

    base_dir = Path(args.base).expanduser()
    if not base_dir.exists():
        print(f"Error: base directory {base_dir} does not exist. Run 'bestman init' first.")
        sys.exit(1)

    parent = Path(args.dest) if args.dest else base_dir.parent

    for name, days, total in INSTANCES:
        dest_dir = parent / f".{name}"
        create_instance(dest_dir, days, total, base_dir)

    print("\nDone! Usage examples:")
    for name, days, total in INSTANCES:
        print(f"  BESTMAN_HOME={parent}/.{name} python -m bestman")


if __name__ == "__main__":
    main()
