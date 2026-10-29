"""
Ultron SQLite Database Manager
Tracks application usage, screen time, network data usage, and voice command logs.
"""
import sqlite3
import datetime
from typing import Dict, List, Any, Optional
from config import DB_PATH

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # App session intervals
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process_name TEXT NOT NULL,
                    app_title TEXT,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    duration_seconds REAL NOT NULL,
                    bytes_sent INTEGER DEFAULT 0,
                    bytes_recv INTEGER DEFAULT 0,
                    date_str TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_date ON app_sessions(date_str)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_process ON app_sessions(process_name)")

            # Command history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commands_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_text TEXT NOT NULL,
                    command_type TEXT,
                    execution_status TEXT,
                    execution_result TEXT
                )
            """)

            # Key-value persistent settings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def log_app_session(self, process_name: str, app_title: str, start_time: datetime.datetime, 
                        end_time: datetime.datetime, duration_seconds: float, 
                        bytes_sent: int = 0, bytes_recv: int = 0):
        if duration_seconds <= 0.2:
            return
        date_str = start_time.strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO app_sessions 
                (process_name, app_title, start_time, end_time, duration_seconds, bytes_sent, bytes_recv, date_str)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (process_name, app_title[:200], start_time.isoformat(), end_time.isoformat(), 
                  duration_seconds, bytes_sent, bytes_recv, date_str))
            conn.commit()

    def log_command(self, raw_text: str, command_type: str, status: str, result: str = ""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO commands_log (raw_text, command_type, execution_status, execution_result)
                VALUES (?, ?, ?, ?)
            """, (raw_text, command_type, status, result[:500]))
            conn.commit()

    def get_daily_screen_time(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        if not target_date:
            target_date = datetime.date.today().strftime("%Y-%m-%d")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    process_name,
                    SUM(duration_seconds) as total_seconds,
                    SUM(bytes_sent + bytes_recv) as total_bytes
                FROM app_sessions
                WHERE date_str = ?
                GROUP BY process_name
                ORDER BY total_seconds DESC
            """, (target_date,))
            rows = cursor.fetchall()

            total_screen_time = sum(r["total_seconds"] for r in rows) if rows else 0
            app_breakdown = [
                {
                    "process_name": r["process_name"],
                    "seconds": round(r["total_seconds"], 1),
                    "minutes": round(r["total_seconds"] / 60.0, 1),
                    "hours": round(r["total_seconds"] / 3600.0, 2),
                    "bytes": r["total_bytes"] or 0
                }
                for r in rows
            ]

            return {
                "date": target_date,
                "total_seconds": round(total_screen_time, 1),
                "total_minutes": round(total_screen_time / 60.0, 1),
                "total_hours": round(total_screen_time / 3600.0, 2),
                "apps": app_breakdown
            }

    def get_monthly_screen_time(self, target_month: Optional[str] = None) -> Dict[str, Any]:
        if not target_month:
            target_month = datetime.date.today().strftime("%Y-%m")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    process_name,
                    SUM(duration_seconds) as total_seconds,
                    SUM(bytes_sent + bytes_recv) as total_bytes
                FROM app_sessions
                WHERE date_str LIKE ?
                GROUP BY process_name
                ORDER BY total_seconds DESC
            """, (f"{target_month}%",))
            app_rows = cursor.fetchall()

            cursor.execute("""
                SELECT 
                    date_str,
                    SUM(duration_seconds) as total_seconds,
                    SUM(bytes_sent + bytes_recv) as total_bytes
                FROM app_sessions
                WHERE date_str LIKE ?
                GROUP BY date_str
                ORDER BY date_str ASC
            """, (f"{target_month}%",))
            daily_rows = cursor.fetchall()

            total_seconds = sum(r["total_seconds"] for r in app_rows) if app_rows else 0
            
            return {
                "month": target_month,
                "total_seconds": round(total_seconds, 1),
                "total_hours": round(total_seconds / 3600.0, 2),
                "apps": [
                    {
                        "process_name": r["process_name"],
                        "hours": round(r["total_seconds"] / 3600.0, 2),
                        "minutes": round(r["total_seconds"] / 60.0, 1),
                        "bytes": r["total_bytes"] or 0
                    }
                    for r in app_rows
                ],
                "daily_trend": [
                    {
                        "date": r["date_str"],
                        "hours": round(r["total_seconds"] / 3600.0, 2),
                        "minutes": round(r["total_seconds"] / 60.0, 1),
                        "bytes": r["total_bytes"] or 0
                    }
                    for r in daily_rows
                ]
            }

    def get_data_usage_summary(self) -> Dict[str, Any]:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        month_str = datetime.date.today().strftime("%Y-%m")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    process_name,
                    SUM(bytes_sent) as sent,
                    SUM(bytes_recv) as recv,
                    SUM(bytes_sent + bytes_recv) as total
                FROM app_sessions
                WHERE date_str = ?
                GROUP BY process_name
                ORDER BY total DESC
            """, (today_str,))
            today_apps = cursor.fetchall()

            cursor.execute("""
                SELECT 
                    process_name,
                    SUM(bytes_sent) as sent,
                    SUM(bytes_recv) as recv,
                    SUM(bytes_sent + bytes_recv) as total
                FROM app_sessions
                WHERE date_str LIKE ?
                GROUP BY process_name
                ORDER BY total DESC
            """, (f"{month_str}%",))
            month_apps = cursor.fetchall()

            return {
                "daily": {
                    "total_bytes": sum(r["total"] for r in today_apps) if today_apps else 0,
                    "apps": [
                        {"process_name": r["process_name"], "bytes_sent": r["sent"], "bytes_recv": r["recv"], "total_bytes": r["total"]}
                        for r in today_apps
                    ]
                },
                "monthly": {
                    "total_bytes": sum(r["total"] for r in month_apps) if month_apps else 0,
                    "apps": [
                        {"process_name": r["process_name"], "bytes_sent": r["sent"], "bytes_recv": r["recv"], "total_bytes": r["total"]}
                        for r in month_apps
                    ]
                }
            }

    def get_recent_commands(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, timestamp, raw_text, command_type, execution_status, execution_result
                FROM commands_log
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_full_dashboard_data(self) -> Dict[str, Any]:
        return {
            "daily_screen_time": self.get_daily_screen_time(),
            "monthly_screen_time": self.get_monthly_screen_time(),
            "data_usage": self.get_data_usage_summary(),
            "recent_commands": self.get_recent_commands(15)
        }
