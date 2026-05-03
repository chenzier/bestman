"""SQLite state management for bestman."""
import sqlite3
from datetime import date
from pathlib import Path


class BestmanState:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path.home() / ".bestman" / "bestman.db"
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()
        self._migrate()

    SCHEMA_VERSION = 2

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

    def record_day(self, day, completed=1, extra=0, task_done="", used_skip=0):
        self.conn.execute(
            "INSERT OR REPLACE INTO days (date, completed, extra, task_done, used_skip) VALUES (?, ?, ?, ?, ?)",
            (day, completed, extra, task_done, used_skip),
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
        self.conn.commit()

    def close(self):
        self.conn.close()
