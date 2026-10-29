"""
Ultron System Commands & OS Automation
Controls system volume, media, screenshots, lock screen, and system info.
"""
import os
import time
import datetime
import ctypes
import subprocess
import pyautogui
import psutil
from pathlib import Path
from typing import Tuple, Dict, Any

class SystemCommands:
    def __init__(self):
        pyautogui.FAILSAFE = False

    def handle_volume(self, action: str) -> Tuple[bool, str]:
        act = action.lower()
        if "up" in act or "raise" in act or "increase" in act:
            for _ in range(5):
                pyautogui.press("volumeup")
            return True, "Increased volume"
        elif "down" in act or "lower" in act or "decrease" in act:
            for _ in range(5):
                pyautogui.press("volumedown")
            return True, "Decreased volume"
        elif "mute" in act:
            pyautogui.press("volumemute")
            return True, "Toggled mute"
        return False, "Unknown volume command"

    def handle_media(self, action: str) -> Tuple[bool, str]:
        act = action.lower()
        if "play" in act or "pause" in act or "resume" in act:
            pyautogui.press("playpause")
            return True, "Toggled media playback"
        elif "next" in act or "skip" in act:
            pyautogui.press("nexttrack")
            return True, "Skipped to next track"
        elif "previous" in act or "back" in act:
            pyautogui.press("prevtrack")
            return True, "Returned to previous track"
        return False, "Unknown media action"

    def take_screenshot(self) -> Tuple[bool, str]:
        try:
            pictures_dir = Path(os.environ.get("USERPROFILE", "C:\\Users\\Default")) / "Pictures" / "Ultron_Screenshots"
            pictures_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = pictures_dir / f"screenshot_{timestamp}.png"

            screenshot = pyautogui.screenshot()
            screenshot.save(str(file_path))
            return True, f"Screenshot saved to {file_path.name}"
        except Exception as e:
            return False, f"Screenshot failed: {e}"

    def lock_workstation(self) -> Tuple[bool, str]:
        try:
            ctypes.windll.user32.LockWorkStation()
            return True, "Locking workstation"
        except Exception as e:
            return False, f"Failed to lock workstation: {e}"

    def show_desktop(self) -> Tuple[bool, str]:
        try:
            pyautogui.hotkey('win', 'd')
            return True, "Toggled desktop view"
        except Exception as e:
            return False, f"Failed to show desktop: {e}"

    def get_system_status(self) -> Tuple[bool, str]:
        try:
            cpu = psutil.cpu_percent(interval=0.2)
            ram = psutil.virtual_memory().percent
            battery = psutil.sensors_battery()
            bat_str = f", battery at {int(battery.percent)} percent" if battery else ""
            
            now = datetime.datetime.now().strftime("%I:%M %p")
            msg = f"System online. Time is {now}. CPU usage is {int(cpu)} percent, memory at {int(ram)} percent{bat_str}."
            return True, msg
        except Exception as e:
            return False, f"Could not query system status: {e}"

    def get_time(self) -> Tuple[bool, str]:
        now = datetime.datetime.now().strftime("%I:%M %p")
        return True, f"The current time is {now}"

    def get_date(self) -> Tuple[bool, str]:
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        return True, f"Today is {today}"

    def shutdown_pc(self, delay_seconds: int = 1) -> Tuple[bool, str]:
        """Initiates Windows shutdown after a brief delay."""
        try:
            cmd = f"shutdown /s /t {max(0, int(delay_seconds))} /f"
            subprocess.Popen(cmd, shell=True)
            return True, "Shutting down the system. Goodbye, boss."
        except Exception as e:
            return False, f"Failed to initiate shutdown: {e}"

    def restart_pc(self, delay_seconds: int = 1) -> Tuple[bool, str]:
        """Initiates Windows restart after a brief delay."""
        try:
            cmd = f"shutdown /r /t {max(0, int(delay_seconds))} /f"
            subprocess.Popen(cmd, shell=True)
            return True, "Restarting the system. I will be back shortly, boss."
        except Exception as e:
            return False, f"Failed to initiate restart: {e}"

    def sleep_pc(self) -> Tuple[bool, str]:
        """Puts Windows into sleep/standby mode."""
        try:
            # SetSuspendState(bHibernate=False, bForce=False, bWakeupEventsDisabled=False)
            powrprof = ctypes.windll.powrprof
            powrprof.SetSuspendState.argtypes = [ctypes.c_bool, ctypes.c_bool, ctypes.c_bool]
            powrprof.SetSuspendState.restype = ctypes.c_bool
            res = powrprof.SetSuspendState(False, False, False)
            if not res:
                ctypes.windll.kernel32.SetSystemPowerState(True, False)
            return True, "Entering sleep mode. Goodnight, boss."
        except Exception as e:
            try:
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                return True, "Entering sleep mode. Goodnight, boss."
            except Exception as e2:
                return False, f"Failed to enter sleep mode: {e2}"

    def cancel_shutdown(self) -> Tuple[bool, str]:
        """Aborts any scheduled Windows shutdown or restart."""
        try:
            subprocess.Popen("shutdown /a", shell=True)
            return True, "Shutdown aborted. System operations remain active, boss."
        except Exception as e:
            return False, f"Failed to cancel shutdown: {e}"
