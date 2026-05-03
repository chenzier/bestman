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
        cursor = self.conn.execute("PRAGMA table_info(voyage_logs)")
        columns = {row[1] for row in cursor.fetchall()}
        if "event_type" not in columns:
            self.conn.execute(
                "ALTER TABLE voyage_logs ADD COLUMN event_type TEXT NOT NULL DEFAULT 'narrative'"
            )

    def record_day(self, day, completed=1, extra=0, task_done=""):
        self.conn.execute(
            "INSERT OR REPLACE INTO days (date, completed, extra, task_done) VALUES (?, ?, ?, ?)",
            (day, completed, extra, task_done),
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

    def close(self):
        self.conn.close()
