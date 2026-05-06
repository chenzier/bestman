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

    SCHEMA_VERSION = 5

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

    def close(self):
        self.conn.close()
