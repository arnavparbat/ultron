"""
Ultron Foreground App & Screen Time Tracker
Continuously monitors the active foreground window, logs durations, and monitors network usage.
"""
import time
import datetime
import threading
import psutil
import win32gui
import win32process
from typing import Optional, Dict
from database import Database
from config import TRACKER_INTERVAL_SEC, NETWORK_TRACKING_ENABLED

class UsageTracker:
    def __init__(self, db: Database):
        self.db = db
        self.running = False
        self.thread: Optional[threading.Thread] = None

        # Current active state
        self.current_process: Optional[str] = None
        self.current_title: str = ""
        self.session_start_time: Optional[datetime.datetime] = None
        self.last_check_time: Optional[float] = None

        # Network tracking baseline
        self.last_net_io = psutil.net_io_counters() if NETWORK_TRACKING_ENABLED else None
        self.lock = threading.Lock()

    def get_foreground_info(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid > 0:
                    try:
                        proc = psutil.Process(pid)
                        name = proc.name().lower()
                        if name.endswith(".exe"):
                            name = name[:-4]
                        return name, title
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

            # Fallback: scan top visible windows
            top_proc = None
            def enum_cb(h, _):
                nonlocal top_proc
                if top_proc:
                    return
                if win32gui.IsWindowVisible(h):
                    t = win32gui.GetWindowText(h)
                    if t and t not in ["Program Manager", ""]:
                        _, p = win32process.GetWindowThreadProcessId(h)
                        try:
                            p_name = psutil.Process(p).name().lower().replace(".exe", "")
                            if p_name not in ["system", "idle"]:
                                top_proc = (p_name, t)
                        except Exception:
                            pass
            try:
                win32gui.EnumWindows(enum_cb, None)
            except Exception:
                pass

            if top_proc:
                return top_proc

            return "explorer", "Windows Desktop"
        except Exception:
            return "explorer", "Windows Desktop"

    def _flush_current_session(self):
        if not self.current_process or not self.session_start_time:
            return

        now = datetime.datetime.now()
        duration = (now - self.session_start_time).total_seconds()

        bytes_sent = 0
        bytes_recv = 0

        if NETWORK_TRACKING_ENABLED and self.last_net_io:
            try:
                curr_net = psutil.net_io_counters()
                bytes_sent = max(0, curr_net.bytes_sent - self.last_net_io.bytes_sent)
                bytes_recv = max(0, curr_net.bytes_recv - self.last_net_io.bytes_recv)
                self.last_net_io = curr_net
            except Exception:
                pass

        if duration >= 0.5:
            self.db.log_app_session(
                process_name=self.current_process,
                app_title=self.current_title,
                start_time=self.session_start_time,
                end_time=now,
                duration_seconds=duration,
                bytes_sent=bytes_sent,
                bytes_recv=bytes_recv
            )

        # Reset session start
        self.session_start_time = now

    def _run_loop(self):
        self.last_check_time = time.time()
        flush_counter = 0

        while self.running:
            try:
                proc_name, title = self.get_foreground_info()

                with self.lock:
                    if proc_name and proc_name != self.current_process:
                        # Process switched, flush old session
                        self._flush_current_session()
                        self.current_process = proc_name
                        self.current_title = title
                        self.session_start_time = datetime.datetime.now()
                    elif proc_name and proc_name == self.current_process:
                        self.current_title = title
                        flush_counter += 1
                        # Periodically flush every 10 seconds
                        if flush_counter >= 10:
                            self._flush_current_session()
                            flush_counter = 0

            except Exception:
                pass

            time.sleep(TRACKER_INTERVAL_SEC)

        # Loop ended, final flush
        with self.lock:
            self._flush_current_session()

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="UltronUsageTracker")
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
