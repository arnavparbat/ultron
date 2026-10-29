r"""
Ultron Windows Auto-Start Manager
Configures HKCU\\Software\Microsoft\Windows\CurrentVersion\Run registry key
for silent background startup on Windows boot.
"""
import sys
import os
import winreg
from pathlib import Path

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "UltronAssistant"

def get_run_key(write: bool = False):
    access = winreg.KEY_SET_VALUE if write else winreg.KEY_READ
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, access)

def is_autostart_enabled() -> bool:
    try:
        with get_run_key(write=False) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except Exception:
        return False

def enable_autostart(command_path: str = "") -> bool:
    if not command_path:
        # Default to start.bat in project root
        root_dir = Path(__file__).resolve().parent.parent
        start_bat = root_dir / "start.bat"
        command_path = f'"{start_bat}" --silent'

    try:
        with get_run_key(write=True) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command_path)
            print(f"[Autostart] Registered {APP_NAME} -> {command_path}")
            return True
    except Exception as e:
        print(f"[Autostart] Failed to register: {e}")
        return False

def disable_autostart() -> bool:
    try:
        with get_run_key(write=True) as key:
            winreg.DeleteValue(key, APP_NAME)
            print(f"[Autostart] Removed {APP_NAME} from Windows startup.")
            return True
    except FileNotFoundError:
        return True
    except Exception as e:
        print(f"[Autostart] Failed to remove autostart: {e}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--enable", action="store_true", help="Enable auto-start on boot")
    parser.add_argument("--disable", action="store_true", help="Disable auto-start on boot")
    parser.add_argument("--status", action="store_true", help="Check auto-start status")
    args = parser.parse_args()

    if args.enable:
        enable_autostart()
    elif args.disable:
        disable_autostart()
    else:
        print("Autostart status:", "ENABLED" if is_autostart_enabled() else "DISABLED")



