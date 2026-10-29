"""
Ultron App Launcher & Alias Manager
Scans Windows Start Menu, Desktop shortcuts, and common applications.
Builds an alias map and provides fuzzy matching via rapidfuzz.
"""
import os
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple
from rapidfuzz import process, fuzz
from config import ALIASES_PATH, CUSTOM_ALIASES_PATH

class AppLauncher:
    def __init__(self, alias_path=ALIASES_PATH, custom_alias_path=CUSTOM_ALIASES_PATH):
        self.alias_path = Path(alias_path)
        self.custom_alias_path = Path(custom_alias_path)
        self.custom_aliases: Dict[str, str] = {}
        self.aliases: Dict[str, str] = {}
        self.load_custom_aliases()
        self.load_or_scan()

    def get_standard_system_apps(self) -> Dict[str, str]:
        """Built-in Windows utilities and standard apps."""
        chrome_exe = "chrome.exe"
        for p in [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
        ]:
            if os.path.exists(p):
                chrome_exe = p
                break

        edge_exe = "msedge.exe"
        for p in [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")
        ]:
            if os.path.exists(p):
                edge_exe = p
                break

        brave_exe = "brave.exe"
        for p in [
            os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe")
        ]:
            if os.path.exists(p):
                brave_exe = p
                break

        firefox_exe = "firefox.exe"
        for p in [
            os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe")
        ]:
            if os.path.exists(p):
                firefox_exe = p
                break

        return {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "terminal": "wt.exe",
            "windows terminal": "wt.exe",
            "powershell": "powershell.exe",
            "file explorer": "explorer.exe",
            "explorer": "explorer.exe",
            "my pc": "explorer.exe",
            "paint": "mspaint.exe",
            "task manager": "taskmgr.exe",
            "settings": "ms-settings:",
            "windows settings": "ms-settings:",
            "control panel": "control.exe",
            "chrome": chrome_exe,
            "google chrome": chrome_exe,
            "edge": edge_exe,
            "microsoft edge": edge_exe,
            "brave": brave_exe,
            "firefox": firefox_exe,
            "spotify": "spotify.exe",
            "discord": "discord.exe",
            "steam": "steam.exe",
            "vs code": "code.cmd",
            "visual studio code": "code.cmd",
            "code": "code.cmd"
        }

    def scan_shortcuts(self) -> Dict[str, str]:
        """Scans Windows Start Menu and Desktop shortcuts."""
        shortcuts: Dict[str, str] = {}

        search_dirs = [
            Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("USERPROFILE", "")) / "Desktop",
            Path("C:\\Users\\Public\\Desktop")
        ]

        # Scan for .lnk and .url files
        for s_dir in search_dirs:
            if not s_dir.exists():
                continue
            for root, _, files in os.walk(s_dir):
                for f in files:
                    if f.lower().endswith((".lnk", ".url")):
                        full_path = os.path.join(root, f)
                        # Clean name: remove extension and unwanted suffixes
                        clean_name = Path(f).stem.lower().strip()
                        clean_name = clean_name.replace(" - shortcut", "").replace(" shortcut", "")
                        # Filter out uninstallers and helper files
                        if any(bad in clean_name for bad in ["uninstall", "remove", "setup", "update", "documentation", "readme"]):
                            continue
                        
                        shortcuts[clean_name] = full_path

        return shortcuts

    def build_aliases(self) -> Dict[str, str]:
        """Combines system apps and scanned shortcuts."""
        aliases = self.get_standard_system_apps()
        scanned = self.scan_shortcuts()
        aliases.update(scanned)
        return aliases

    def load_custom_aliases(self):
        """Loads user-added custom application aliases."""
        if self.custom_alias_path.exists():
            try:
                with open(self.custom_alias_path, "r", encoding="utf-8") as f:
                    self.custom_aliases = json.load(f)
                return
            except Exception as e:
                print(f"[AppLauncher] Error loading custom aliases: {e}")
        self.custom_aliases = {}

    def save_custom_aliases(self):
        """Saves custom application aliases to disk."""
        try:
            self.custom_alias_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.custom_alias_path, "w", encoding="utf-8") as f:
                json.dump(self.custom_aliases, f, indent=2)
        except Exception as e:
            print(f"[AppLauncher] Error saving custom aliases: {e}")

    def load_or_scan(self, force_rescan: bool = False):
        self.load_custom_aliases()
        if not force_rescan and self.alias_path.exists():
            try:
                with open(self.alias_path, "r", encoding="utf-8") as f:
                    self.aliases = json.load(f)
                # Always merge in user custom aliases
                self.aliases.update(self.custom_aliases)
                return
            except Exception:
                pass

        # Rescan and save
        self.aliases = self.build_aliases()
        # Ensure custom aliases are preserved after rescan
        self.aliases.update(self.custom_aliases)
        self.save_aliases()

    def save_aliases(self):
        try:
            self.alias_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.alias_path, "w", encoding="utf-8") as f:
                json.dump(self.aliases, f, indent=2)
        except Exception as e:
            print(f"[AppLauncher] Error saving aliases: {e}")

    def add_custom_alias(self, alias_name: str, app_path: str) -> Tuple[bool, str]:
        clean_name = alias_name.lower().strip()
        clean_path = app_path.strip().strip('"\'')
        if not clean_name:
            return False, "Alias name cannot be empty."
        if not clean_path:
            return False, "Application path cannot be empty."

        self.custom_aliases[clean_name] = clean_path
        self.save_custom_aliases()

        self.aliases[clean_name] = clean_path
        self.save_aliases()

        print(f"[AppLauncher] Registered custom app alias '{clean_name}' -> '{clean_path}'")
        return True, f"Application '{clean_name}' registered successfully."

    def remove_custom_alias(self, alias_name: str) -> Tuple[bool, str]:
        clean_name = alias_name.lower().strip()
        found = False
        if clean_name in self.custom_aliases:
            del self.custom_aliases[clean_name]
            self.save_custom_aliases()
            found = True

        if clean_name in self.aliases:
            del self.aliases[clean_name]
            self.save_aliases()
            found = True

        if found:
            print(f"[AppLauncher] Removed custom alias '{clean_name}'")
            return True, f"Application alias '{clean_name}' removed."
        return False, f"Alias '{clean_name}' not found."

    def find_app(self, query: str, threshold: int = 65) -> Optional[Tuple[str, str, float]]:
        """
        Fuzzy match app name. Returns (matched_alias, path, score) or None.
        Prioritizes user custom aliases, handles conversational filler.
        """
        raw_q = query.lower().strip()
        # Clean filler articles and terms: "the", "my", "app", "application", "for me", "please"
        clean_q = re.sub(r"^(?:the\s+|my\s+)", "", raw_q)
        clean_q = re.sub(r"\s+(?:app|application|program|software)$", "", clean_q)
        clean_q = re.sub(r"\s+(?:for me|please)$", "", clean_q).strip()
        # Clean browser prepositional phrases (e.g. "in chrome", "on chrome")
        clean_q = re.sub(r"\s+(?:in\s+(?:google\s+)?chrome|on\s+(?:google\s+)?chrome|in\s+(?:the\s+)?browser|on\s+(?:the\s+)?browser|in\s+edge|in\s+brave)$", "", clean_q).strip()

        # 1. Direct exact match in custom aliases (check raw & cleaned)
        for q in [clean_q, raw_q]:
            if q in self.custom_aliases:
                return q, self.custom_aliases[q], 100.0

        # 2. Direct exact match in all aliases
        for q in [clean_q, raw_q]:
            if q in self.aliases:
                return q, self.aliases[q], 100.0

        # 3. Fuzzy match against custom aliases first
        if self.custom_aliases:
            custom_choices = list(self.custom_aliases.keys())
            custom_match = process.extractOne(clean_q, custom_choices, scorer=fuzz.token_sort_ratio)
            if custom_match and custom_match[1] >= threshold:
                matched_name = custom_match[0]
                return matched_name, self.custom_aliases[matched_name], custom_match[1]

        choices = list(self.aliases.keys())
        if not choices:
            return None

        # 4. Fuzzy match with token_sort_ratio (prevents single-token choices from matching any sentence containing that word)
        best_match = process.extractOne(clean_q, choices, scorer=fuzz.token_sort_ratio)
        if best_match and best_match[1] >= threshold:
            matched_name = best_match[0]
            return matched_name, self.aliases[matched_name], best_match[1]

        # 5. Secondary attempt with WRatio
        alt_match = process.extractOne(clean_q, choices, scorer=fuzz.WRatio)
        if alt_match and alt_match[1] >= max(threshold, 75):
            matched_name = alt_match[0]
            return matched_name, self.aliases[matched_name], alt_match[1]

        return None

    def launch(self, query: str) -> Tuple[bool, str]:
        """
        Finds and launches the specified app.
        """
        match = self.find_app(query)
        if not match:
            # Last ditch attempt: try running query directly if it might be an executable or URI
            try:
                clean_q = query.strip().strip('"\'')
                if clean_q.endswith(":") or "." in clean_q or os.path.exists(clean_q):
                    os.startfile(clean_q)
                    return True, f"Launched {query}"
            except Exception:
                pass
            return False, f"Could not find application '{query}'"

        alias_name, target, score = match
        try:
            target = target.strip().strip('"\'')
            # Check if URI or special command
            if target.startswith("ms-settings:") or target.endswith(":"):
                os.startfile(target)
                return True, f"Opened {alias_name}"

            if target.lower().endswith((".lnk", ".url")):
                os.startfile(target)
                return True, f"Launched {alias_name}"

            # General executable / script
            if not os.path.exists(target):
                import shutil
                w = shutil.which(target)
                if w:
                    target = w
                elif target.lower() in ["chrome", "chrome.exe"]:
                    for cp in [
                        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
                    ]:
                        if os.path.exists(cp):
                            target = cp
                            break

            if os.path.exists(target):
                try:
                    os.startfile(target)
                except Exception:
                    work_dir = os.path.dirname(target) if os.path.dirname(target) else None
                    subprocess.Popen(f'"{target}"', shell=True, cwd=work_dir)
                return True, f"Launched {alias_name}"
            else:
                # Try launching directly by command name via subprocess
                subprocess.Popen(target, shell=True)
                return True, f"Launched {alias_name}"

        except Exception as e:
            return False, f"Failed to launch {alias_name}: {str(e)}"

