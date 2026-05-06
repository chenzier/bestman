"""SQLite state management for bestman."""
import sqlite3
from datetime import date
from pathlib import Path

from bestman.core.config import BESTMAN_HOME


class BestmanState:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = BESTMAN_HOME / "bestman.db"
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()
        self._migrate()

    SCHEMA_VERSION = 6

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS days (
                date TEXT PRIMARY KEY,
                completed INTEGER NOT NULL DEFAULT 0,
                extra INTEGER NOT NULL DEFAULT 0,
                task_done TEXT DEFAULT '',
                used_skip INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS voyage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                text TEXT NOT NULL DEFAULT '',
                event_type TEXT NOT NULL DEFAULT 'narrative',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        """Run schema migrations for existing databases."""
        # v0.2: add event_type column to voyage_logs
        cursor = self.conn.execute("PRAGMA table_info(voyage_logs)")
        columns = {row[1] for row in cursor.fetchall()}
        if "event_type" not in columns:
            self.conn.execute(
                "ALTER TABLE voyage_logs ADD COLUMN event_type TEXT NOT NULL DEFAULT 'narrative'"
            )

        # v0.3: add skip_tokens table
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skip_tokens'"
        )
        if not cursor.fetchone():
            self.conn.execute("""
                CREATE TABLE skip_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    earned_date TEXT NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

        # v0.4: add coins_earned column to days
        cursor = self.conn.execute("PRAGMA table_info(days)")
        columns = {row[1] for row in cursor.fetchall()}
        if "coins_earned" not in columns:
            self.conn.execute(
                "ALTER TABLE days ADD COLUMN coins_earned INTEGER NOT NULL DEFAULT 0"
            )

        # v0.4: add treasures table
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='treasures'"
        )
        if not cursor.fetchone():
            self.conn.execute("""
                CREATE TABLE treasures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    coins INTEGER NOT NULL,
                    discovered_date TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

        # v0.5: add weights table
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='weights'"
        )
        if not cursor.fetchone():
            self.conn.execute("""
                CREATE TABLE weights (
                    date TEXT PRIMARY KEY,
                    weight_kg REAL NOT NULL,
                    note TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

        # v0.5: add plan_overrides table
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='plan_overrides'"
        )
        if not cursor.fetchone():
            self.conn.execute("""
                CREATE TABLE plan_overrides (
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

        # ── v2.2: crew tables ──────────────────────────────────
        # v2.2: crew — 已招募船员
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crew'"
        )
        if not cursor.fetchone():
            self.conn.execute("""
                CREATE TABLE crew (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    rarity TEXT NOT NULL DEFAULT 'common',
                    level INTEGER NOT NULL DEFAULT 1,
                    xp INTEGER NOT NULL DEFAULT 0,
                    mood INTEGER NOT NULL DEFAULT 70,
                    hired_date TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    is_main INTEGER NOT NULL DEFAULT 0,
                    skill_cooldown_until TEXT,
                    recalled_from TEXT
                )
            """)

        # v2.2: crew_dialogues — 对话历史
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crew_dialogues'"
        )
        if not cursor.fetchone():
            self.conn.execute("""
                CREATE TABLE crew_dialogues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crew_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    user_reply TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (crew_id) REFERENCES crew(id)
                )
            """)

        # v2.2: crew_quests — 每周任务
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crew_quests'"
        )
        if not cursor.fetchone():
            self.conn.execute("""
                CREATE TABLE crew_quests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crew_id INTEGER NOT NULL,
                    week_start_date TEXT NOT NULL,
                    quest_type TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    target INTEGER NOT NULL DEFAULT 1,
                    completed INTEGER NOT NULL DEFAULT 0,
                    reward_claimed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (crew_id) REFERENCES crew(id)
                )
            """)

        # v2.2: crew_recruit_history — 招募历史（用于保底机制）
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crew_recruit_history'"
        )
        if not cursor.fetchone():
            self.conn.execute("""
                CREATE TABLE crew_recruit_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    role_id TEXT,
                    rarity TEXT NOT NULL,
                    method TEXT NOT NULL DEFAULT 'random',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

    # ── 基础数据操作（不变）────────────────────────────────────

    def record_day(self, day, completed=1, extra=0, task_done="", used_skip=0, coins_earned=0):
        self.conn.execute(
            "INSERT OR REPLACE INTO days (date, completed, extra, task_done, used_skip, coins_earned) VALUES (?, ?, ?, ?, ?, ?)",
            (day, completed, extra, task_done, used_skip, coins_earned),
        )
        self.conn.commit()

    def today_recorded(self, day=None):
        if day is None:
            day = date.today().isoformat()
        cursor = self.conn.execute(
            "SELECT 1 FROM days WHERE date=? AND completed=1", (day,)
        )
        return cursor.fetchone() is not None

    def get_tiles_revealed(self):
        cursor = self.conn.execute(
            "SELECT COALESCE(SUM(completed), 0) + COALESCE(SUM(extra), 0) FROM days"
        )
        return cursor.fetchone()[0]

    def get_completed_days(self):
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM days WHERE completed=1"
        )
        return cursor.fetchone()[0]

    def get_streak(self, reference_date=None):
        """计算连续打卡天数（包括 used_skip=1 的天）。

        从 reference_date 往回数，统计连续满足 completed=1 或 used_skip=1 的天数。
        如果最近记录与 reference_date 的间隔超过 1 天，返回 0。

        Args:
            reference_date: 参考日期字符串 (YYYY-MM-DD)，默认今天

        Returns:
            int: 连续天数
        """
        if reference_date is None:
            reference_date = date.today().isoformat()

        ref = date.fromisoformat(reference_date)

        rows = self.conn.execute(
            "SELECT date FROM days WHERE date <= ? AND (completed=1 OR used_skip=1) ORDER BY date DESC",
            (reference_date,),
        ).fetchall()

        if not rows:
            return 0

        most_recent = date.fromisoformat(rows[0][0])
        if (ref - most_recent).days > 1:
            return 0

        streak = 1
        for i in range(len(rows) - 1):
            curr = date.fromisoformat(rows[i][0])
            prev = date.fromisoformat(rows[i + 1][0])
            if (curr - prev).days == 1:
                streak += 1
            else:
                break

        return streak

    def add_skip_token(self, earned_date):
        """发放一枚跳过令牌。"""
        self.conn.execute(
            "INSERT INTO skip_tokens (earned_date) VALUES (?)",
            (earned_date,),
        )
        self.conn.commit()

    def get_available_skip_tokens(self):
        """返回可用跳过令牌数。"""
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM skip_tokens WHERE used=0"
        )
        return cursor.fetchone()[0]

    def use_skip_token(self):
        """使用一枚跳过令牌。

        Returns:
            bool: True 表示使用成功，False 表示无可用令牌
        """
        cursor = self.conn.execute(
            "SELECT id FROM skip_tokens WHERE used=0 ORDER BY id ASC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            self.conn.execute(
                "UPDATE skip_tokens SET used=1 WHERE id=?", (row[0],)
            )
            self.conn.commit()
            return True
        return False

    def save_log(self, day, text, event_type="narrative"):
        self.conn.execute(
            "INSERT INTO voyage_logs (date, text, event_type) VALUES (?, ?, ?)",
            (day, text, event_type),
        )
        self.conn.commit()

    def get_logs(self, limit=10):
        cursor = self.conn.execute(
            "SELECT date, text FROM voyage_logs ORDER BY date DESC LIMIT ?",
            (limit,),
        )
        return [{"date": row[0], "text": row[1]} for row in cursor.fetchall()]

    def delete_day(self, day):
        """删除指定日期的所有记录（仅供 --force 测试使用）。"""
        self.conn.execute("DELETE FROM days WHERE date = ?", (day,))
        self.conn.execute("DELETE FROM voyage_logs WHERE date = ?", (day,))
        self.conn.commit()

    def reset_all(self):
        """清空所有数据（仅供测试使用）。"""
        self.conn.execute("DELETE FROM days")
        self.conn.execute("DELETE FROM voyage_logs")
        self.conn.execute("DELETE FROM skip_tokens")
        self.conn.execute("DELETE FROM treasures")
        self.conn.execute("DELETE FROM weights")
        self.conn.execute("DELETE FROM plan_overrides")
        self.conn.execute("DELETE FROM crew")
        self.conn.execute("DELETE FROM crew_dialogues")
        self.conn.execute("DELETE FROM crew_quests")
        self.conn.execute("DELETE FROM crew_recruit_history")
        self.conn.commit()

    def get_total_coins(self):
        """返回累计金币总数。

        Returns:
            int: 所有天的 coins_earned 之和
        """
        cursor = self.conn.execute(
            "SELECT COALESCE(SUM(coins_earned), 0) FROM days"
        )
        return cursor.fetchone()[0]

    def discover_treasure(self, name, treasure_type, coins, discovered_date):
        """记录发现宝藏。

        Args:
            name: 宝藏名称
            treasure_type: 'explicit' 或 'implicit'
            coins: 金币数量
            discovered_date: 发现日期 (YYYY-MM-DD)
        """
        self.conn.execute(
            "INSERT INTO treasures (name, type, coins, discovered_date) VALUES (?, ?, ?, ?)",
            (name, treasure_type, coins, discovered_date),
        )
        self.conn.commit()

    def get_treasures(self):
        """返回已发现的所有宝藏。

        Returns:
            list[dict]: 宝藏记录列表
        """
        cursor = self.conn.execute(
            "SELECT name, type, coins, discovered_date FROM treasures ORDER BY discovered_date ASC"
        )
        return [
            {"name": row[0], "type": row[1], "coins": row[2], "discovered_date": row[3]}
            for row in cursor.fetchall()
        ]

    def record_weight(self, date_str, weight_kg, note=""):
        """记录体重测量。

        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
            weight_kg: 体重（公斤）
            note: 备注
        """
        self.conn.execute(
            "INSERT OR REPLACE INTO weights (date, weight_kg, note) VALUES (?, ?, ?)",
            (date_str, weight_kg, note),
        )
        self.conn.commit()

    def get_weight_history(self, limit=None):
        """获取体重历史，最近的在前面。

        Args:
            limit: 返回条数上限，None 表示全部

        Returns:
            list[dict]: 体重记录列表
        """
        if limit:
            cursor = self.conn.execute(
                "SELECT date, weight_kg, note FROM weights ORDER BY date DESC LIMIT ?",
                (limit,),
            )
        else:
            cursor = self.conn.execute(
                "SELECT date, weight_kg, note FROM weights ORDER BY date DESC"
            )
        return [{"date": row[0], "weight_kg": row[1], "note": row[2]}
                for row in cursor.fetchall()]

    def get_latest_weight(self):
        """获取最近一次体重记录。

        Returns:
            dict | None: {"date", "weight_kg", "note"} 或 None
        """
        cursor = self.conn.execute(
            "SELECT date, weight_kg, note FROM weights ORDER BY date DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return {"date": row[0], "weight_kg": row[1], "note": row[2]}
        return None

    def get_weekly_stats(self, start_date, end_date):
        """获取一周的聚合统计数据。

        Args:
            start_date: 周起始日期 (YYYY-MM-DD)
            end_date: 周结束日期 (YYYY-MM-DD)

        Returns:
            dict: {check_ins, skips, days_count, total_tiles, max_tiles, min_tiles, coins}
        """
        rows = self.conn.execute(
            "SELECT completed, extra, used_skip, coins_earned FROM days "
            "WHERE date >= ? AND date <= ?",
            (start_date, end_date),
        ).fetchall()

        check_ins = sum(1 for r in rows if r[0] > 0)
        skips = sum(1 for r in rows if r[2] == 1)
        tiles_per_day = [r[0] + r[1] for r in rows if r[0] + r[1] > 0]
        total_tiles = sum(tiles_per_day)
        max_tiles = max(tiles_per_day) if tiles_per_day else 0
        min_tiles = min(tiles_per_day) if tiles_per_day else 0
        coins = sum(r[3] for r in rows)

        return {
            "check_ins": check_ins,
            "skips": skips,
            "days_count": len(rows),
            "total_tiles": total_tiles,
            "max_tiles": max_tiles,
            "min_tiles": min_tiles,
            "coins": coins,
        }

    def add_override(self, created_date, field, original_value, override_value, expires_date=None, reason=""):
        """添加计划覆盖（来自 talk 命令的临时修改）。

        Args:
            created_date: 创建日期 (YYYY-MM-DD)
            field: 覆盖字段名，如 'daily_task'
            original_value: 原始值
            override_value: 覆盖值
            expires_date: 过期日期，None 表示手动恢复
            reason: 原因说明

        Returns:
            int: 新记录的 id
        """
        self.conn.execute(
            "INSERT INTO plan_overrides (created_date, expires_date, field, "
            "original_value, override_value, reason) VALUES (?, ?, ?, ?, ?, ?)",
            (created_date, expires_date, field, original_value, override_value, reason),
        )
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_active_overrides(self, field=None, check_date=None):
        """获取活跃的计划覆盖。

        Args:
            field: 按字段名过滤，None 返回所有
            check_date: 检查日期，默认今天

        Returns:
            list[dict]: 活跃覆盖列表
        """
        if check_date is None:
            check_date = date.today().isoformat()

        query = (
            "SELECT id, created_date, expires_date, field, original_value, "
            "override_value, reason FROM plan_overrides "
            "WHERE active = 1 AND (expires_date IS NULL OR expires_date >= ?)"
        )
        params = [check_date]

        if field:
            query += " AND field = ?"
            params.append(field)

        cursor = self.conn.execute(query, params)
        return [
            {
                "id": row[0], "created_date": row[1], "expires_date": row[2],
                "field": row[3], "original_value": row[4], "override_value": row[5],
                "reason": row[6],
            }
            for row in cursor.fetchall()
        ]

    def deactivate_override(self, override_id):
        """停用一条计划覆盖。

        Args:
            override_id: 覆盖记录 id
        """
        self.conn.execute(
            "UPDATE plan_overrides SET active = 0 WHERE id = ?", (override_id,)
        )
        self.conn.commit()

    # ── v2.2: 船员管理方法 ────────────────────────────────────

    def hire_crew(self, role_id, name, rarity, hired_date):
        """招募一名船员。

        Args:
            role_id: 角色 ID（如 "captain"）
            name: 角色名称
            rarity: 稀有度
            hired_date: 招募日期

        Returns:
            int: 新船员的 id
        """
        # 检查是否已拥有该角色
        existing = self.conn.execute(
            "SELECT id FROM crew WHERE role_id=? AND active=1", (role_id,)
        ).fetchone()
        if existing:
            return None

        self.conn.execute(
            "INSERT INTO crew (role_id, name, rarity, mood, hired_date) VALUES (?, ?, ?, 70, ?)",
            (role_id, name, rarity, hired_date),
        )
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def fire_crew(self, crew_id):
        """解雇船员（标记为 inactive）。

        Args:
            crew_id: 船员 id

        Returns:
            dict | None: 被解雇船员信息，含 role_id 和 rarity
        """
        cursor = self.conn.execute(
            "SELECT role_id, rarity FROM crew WHERE id=? AND active=1", (crew_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        self.conn.execute(
            "UPDATE crew SET active=0, recalled_from=NULL WHERE id=?", (crew_id,)
        )
        self.conn.commit()
        return {"role_id": row[0], "rarity": row[1]}

    def recall_crew(self, crew_id, recall_date):
        """召回曾被解雇的船员。

        Args:
            crew_id: 船员 id
            recall_date: 召回日期

        Returns:
            bool: 是否召回成功
        """
        cursor = self.conn.execute(
            "SELECT id FROM crew WHERE id=? AND active=0", (crew_id,)
        )
        if not cursor.fetchone():
            return False

        self.conn.execute(
            "UPDATE crew SET active=1, recalled_from=? WHERE id=?",
            (recall_date, crew_id),
        )
        self.conn.commit()
        return True

    def get_crew(self, crew_id):
        """获取单个船员信息。

        Returns:
            dict | None
        """
        cursor = self.conn.execute(
            "SELECT id, role_id, name, rarity, level, xp, mood, hired_date, "
            "active, is_main, skill_cooldown_until "
            "FROM crew WHERE id=?",
            (crew_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0], "role_id": row[1], "name": row[2], "rarity": row[3],
            "level": row[4], "xp": row[5], "mood": row[6], "hired_date": row[7],
            "active": bool(row[8]), "is_main": bool(row[9]),
            "skill_cooldown_until": row[10],
        }

    def list_crew(self, active_only=True):
        """列出船员。

        Args:
            active_only: 仅返回在船船员

        Returns:
            list[dict]
        """
        if active_only:
            rows = self.conn.execute(
                "SELECT id, role_id, name, rarity, level, xp, mood, hired_date, "
                "is_main, skill_cooldown_until "
                "FROM crew WHERE active=1 ORDER BY is_main DESC, hired_date ASC"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT id, role_id, name, rarity, level, xp, mood, hired_date, "
                "active, is_main, skill_cooldown_until "
                "FROM crew ORDER BY active DESC, is_main DESC, hired_date ASC"
            ).fetchall()

        return [
            {
                "id": r[0], "role_id": r[1], "name": r[2], "rarity": r[3],
                "level": r[4], "xp": r[5], "mood": r[6], "hired_date": r[7],
                "active": bool(r[8]) if len(r) > 9 else True,
                "is_main": bool(r[8]) if len(r) == 9 else bool(r[9] if len(r) > 9 else r[8]),
                "skill_cooldown_until": r[10] if len(r) > 10 else None,
            }
            for r in rows
        ]

    def set_main_crew(self, crew_id):
        """设定主船员。

        Args:
            crew_id: 船员 id

        Returns:
            bool: 是否设置成功
        """
        crew = self.get_crew(crew_id)
        if not crew or not crew["active"]:
            return False

        self.conn.execute("UPDATE crew SET is_main=0")
        self.conn.execute("UPDATE crew SET is_main=1 WHERE id=?", (crew_id,))
        self.conn.commit()
        return True

    def upgrade_crew(self, crew_id, new_level, new_xp):
        """升级船员。

        Args:
            crew_id: 船员 id
            new_level: 新等级
            new_xp: 新经验值
        """
        self.conn.execute(
            "UPDATE crew SET level=?, xp=? WHERE id=?",
            (new_level, new_xp, crew_id),
        )
        self.conn.commit()

    def update_crew_mood(self, crew_id, mood):
        """更新船员情绪值（0-100）。

        Args:
            crew_id: 船员 id
            mood: 新情绪值
        """
        self.conn.execute(
            "UPDATE crew SET mood=MAX(0, MIN(100, ?)) WHERE id=?",
            (mood, crew_id),
        )
        self.conn.commit()

    def decay_crew_mood(self, crew_id, amount):
        """衰减船员情绪值。

        Args:
            crew_id: 船员 id
            amount: 衰减量
        """
        self.conn.execute(
            "UPDATE crew SET mood=MAX(0, mood - ?) WHERE id=?",
            (amount, crew_id),
        )
        self.conn.commit()

    def set_skill_cooldown(self, crew_id, cooldown_until):
        """设置技能冷却截止日期。

        Args:
            crew_id: 船员 id
            cooldown_until: 冷却截止日期 (YYYY-MM-DD)
        """
        self.conn.execute(
            "UPDATE crew SET skill_cooldown_until=? WHERE id=?",
            (cooldown_until, crew_id),
        )
        self.conn.commit()

    def add_crew_dialogue(self, crew_id, date_str, trigger_type, text):
        """记录船员对话。

        Args:
            crew_id: 船员 id
            date_str: 日期
            trigger_type: 触发类型
            text: 对话内容

        Returns:
            int: 新对话 id
        """
        self.conn.execute(
            "INSERT INTO crew_dialogues (crew_id, date, trigger_type, text) VALUES (?, ?, ?, ?)",
            (crew_id, date_str, trigger_type, text),
        )
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_crew_dialogues(self, crew_id=None, limit=20):
        """获取船员对话历史。

        Args:
            crew_id: 船员 id，None 返回所有
            limit: 返回条数上限

        Returns:
            list[dict]
        """
        if crew_id:
            rows = self.conn.execute(
                "SELECT cd.id, cd.crew_id, c.name, cd.date, cd.trigger_type, cd.text "
                "FROM crew_dialogues cd JOIN crew c ON cd.crew_id=c.id "
                "WHERE cd.crew_id=? ORDER BY cd.date DESC LIMIT ?",
                (crew_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT cd.id, cd.crew_id, c.name, cd.date, cd.trigger_type, cd.text "
                "FROM crew_dialogues cd JOIN crew c ON cd.crew_id=c.id "
                "ORDER BY cd.date DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [
            {"id": r[0], "crew_id": r[1], "name": r[2], "date": r[3],
             "trigger_type": r[4], "text": r[5]}
            for r in rows
        ]

    def get_crew_dialogue_count_today(self, crew_id, date_str):
        """获取某船员今天的对话次数。

        Args:
            crew_id: 船员 id
            date_str: 日期

        Returns:
            int
        """
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM crew_dialogues WHERE crew_id=? AND date=?",
            (crew_id, date_str),
        )
        return cursor.fetchone()[0]

    def get_days_since_last_dialogue(self, crew_id, date_str):
        """获取距上次对话的天数。

        Args:
            crew_id: 船员 id
            date_str: 参考日期

        Returns:
            int: 天数，无记录时返回 999
        """
        cursor = self.conn.execute(
            "SELECT date FROM crew_dialogues WHERE crew_id=? ORDER BY date DESC LIMIT 1",
            (crew_id,),
        )
        row = cursor.fetchone()
        if not row:
            return 999
        last_date = date.fromisoformat(row[0])
        ref_date = date.fromisoformat(date_str)
        return (ref_date - last_date).days

    def add_crew_quest(self, crew_id, week_start_date, quest_type, target):
        """添加船员每周任务。

        Args:
            crew_id: 船员 id
            week_start_date: 周起始日期
            quest_type: 任务类型
            target: 完成目标

        Returns:
            int: 新任务 id
        """
        self.conn.execute(
            "INSERT INTO crew_quests (crew_id, week_start_date, quest_type, target) "
            "VALUES (?, ?, ?, ?)",
            (crew_id, week_start_date, quest_type, target),
        )
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def update_quest_progress(self, quest_id, progress):
        """更新任务进度。

        Args:
            quest_id: 任务 id
            progress: 新进度值
        """
        self.conn.execute(
            "UPDATE crew_quests SET progress=? WHERE id=?",
            (progress, quest_id),
        )
        self.conn.commit()

    def complete_quest(self, quest_id):
        """完成任务。

        Args:
            quest_id: 任务 id
        """
        self.conn.execute(
            "UPDATE crew_quests SET completed=1 WHERE id=?",
            (quest_id,),
        )
        self.conn.commit()

    def claim_quest_reward(self, quest_id):
        """领取任务奖励。

        Args:
            quest_id: 任务 id
        """
        self.conn.execute(
            "UPDATE crew_quests SET reward_claimed=1 WHERE id=?",
            (quest_id,),
        )
        self.conn.commit()

    def get_active_quests(self, date_str=None):
        """获取当前周活跃任务。

        Args:
            date_str: 参考日期

        Returns:
            list[dict]
        """
        if date_str is None:
            date_str = date.today().isoformat()

        rows = self.conn.execute(
            "SELECT cq.id, cq.crew_id, c.name, cq.week_start_date, cq.quest_type, "
            "cq.progress, cq.target, cq.completed, cq.reward_claimed "
            "FROM crew_quests cq JOIN crew c ON cq.crew_id=c.id "
            "WHERE cq.week_start_date <= ? AND c.active=1 "
            "ORDER BY cq.completed ASC, cq.week_start_date DESC",
            (date_str,),
        ).fetchall()

        return [
            {
                "id": r[0], "crew_id": r[1], "crew_name": r[2],
                "week_start_date": r[3], "quest_type": r[4],
                "progress": r[5], "target": r[6],
                "completed": bool(r[7]), "reward_claimed": bool(r[8]),
            }
            for r in rows
        ]

    def get_crew_quests(self, crew_id, limit=5):
        """获取某船员的任务历史。

        Args:
            crew_id: 船员 id
            limit: 返回条数

        Returns:
            list[dict]
        """
        rows = self.conn.execute(
            "SELECT id, week_start_date, quest_type, progress, target, completed, reward_claimed "
            "FROM crew_quests WHERE crew_id=? ORDER BY week_start_date DESC LIMIT ?",
            (crew_id, limit),
        ).fetchall()

        return [
            {
                "id": r[0], "week_start_date": r[1], "quest_type": r[2],
                "progress": r[3], "target": r[4],
                "completed": bool(r[5]), "reward_claimed": bool(r[6]),
            }
            for r in rows
        ]

    def add_recruit_history(self, date_str, role_id, rarity, method="random"):
        """记录招募历史（用于保底机制）。

        Args:
            date_str: 日期
            role_id: 角色 ID，None 表示未抽到角色
            rarity: 稀有度
            method: 招募方式
        """
        self.conn.execute(
            "INSERT INTO crew_recruit_history (date, role_id, rarity, method) VALUES (?, ?, ?, ?)",
            (date_str, role_id, rarity, method),
        )
        self.conn.commit()

    def get_consecutive_misses(self, rarity):
        """获取连续未抽中特定稀有度的次数。

        Args:
            rarity: 稀有度（"rare" 或 "legendary"）

        Returns:
            int: 连续未中次数
        """
        rows = self.conn.execute(
            "SELECT rarity FROM crew_recruit_history ORDER BY id DESC"
        ).fetchall()

        count = 0
        for row in rows:
            if row[0] == rarity:
                break
            count += 1
        return count

    def get_crew_count(self):
        """获取当前在船船员数量。

        Returns:
            int
        """
        cursor = self.conn.execute("SELECT COUNT(*) FROM crew WHERE active=1")
        return cursor.fetchone()[0]

    def get_completed_days_count(self):
        """获取累计完成天数（含 used_skip 的天）。

        Returns:
            int
        """
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM days WHERE completed > 0 OR used_skip = 1"
        )
        return cursor.fetchone()[0]

    def close(self):
        self.conn.close()
