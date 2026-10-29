"""
Ultron Command Parser & Dispatcher
Parses voice/text inputs, categorizes intents, coordinates execution, logs to SQLite.
Seamlessly routes conversational questions, weather queries, and general knowledge to the AI Brain.
"""
import re
import urllib.parse
from typing import Tuple, Dict, Any, Callable, Optional
from app_launcher import AppLauncher
from website_opener import WebsiteOpener
from system_commands import SystemCommands
from database import Database
from ai_brain import AIBrain
from folder_manager import FolderManager
from file_manager import FileManager

class CommandParser:
    def __init__(self, db: Database, app_launcher: AppLauncher, website_opener: WebsiteOpener, 
                 system_commands: SystemCommands, ai_brain: Optional[AIBrain] = None,
                 on_ui_event: Optional[Callable[[str, Any], None]] = None,
                 folder_manager: Optional[FolderManager] = None,
                 file_manager: Optional[FileManager] = None):
        self.db = db
        self.app_launcher = app_launcher
        self.website_opener = website_opener
        self.sys_cmds = system_commands
        self.ai_brain = ai_brain
        self.on_ui_event = on_ui_event
        self.folder_manager = folder_manager or FolderManager()
        self.file_manager = file_manager or FileManager()

    def parse_and_execute(self, raw_text: str, is_cancelled: Optional[Callable[[], bool]] = None) -> Tuple[str, str, bool]:
        """
        Executes the parsed command.
        Returns (command_type, speech_response_or_result, success)
        """
        if is_cancelled and is_cancelled():
            return "cancelled", "", False

        text = raw_text.lower().strip()

        # 0. Stand down / Stop / Pause command
        stop_phrases = ["stop", "pause", "be quiet", "shut up", "stop talking", "cancel", "stand down", "halt", "quiet", "silence", "target eliminated", "abort"]
        if text in stop_phrases or any(text == f"ultron {p}" or text == f"hey ultron {p}" for p in stop_phrases):
            msg = "Standing down, boss."
            self.db.log_command(raw_text, "stop", "success", msg)
            return "stop", msg, True

        # 1. Window Mode: Come to me (Bring overlay to top of all screens)
        if any(k in text for k in ["come to me", "come here", "bring overlay", "bring to front", "show on top", "on top", "come front"]):
            if self.on_ui_event:
                self.on_ui_event("window_mode", {"mode": "always-on-top"})
            msg = "Yes boss, coming to you."
            self.db.log_command(raw_text, "window_mode", "success", msg)
            return "window_mode", msg, True

        # 2. Window Mode: Return to Desktop (Only on desktop, behind active windows)
        if any(k in text for k in ["go to desktop", "back to desktop", "return to desktop", "go back to desktop", "go back", "stay on desktop", "desktop mode", "send to desktop"]):
            if self.on_ui_event:
                self.on_ui_event("window_mode", {"mode": "desktop"})
            msg = "Returning to desktop, boss."
            self.db.log_command(raw_text, "window_mode", "success", msg)
            return "window_mode", msg, True

        # 3. Weather queries (Live Real-time Weather)
        if any(k in text for k in ["weather", "temperature", "forecast", "how hot is it", "how cold is it", "is it raining"]):
            if self.ai_brain:
                msg = self.ai_brain.get_weather(raw_text)
            else:
                msg = "Weather telemetry unavailable."
            self.db.log_command(raw_text, "weather", "success", msg)
            return "weather", msg, True

        # 4. Clear conversation memory
        if any(k in text for k in ["clear memory", "reset memory", "forget conversation", "clear chat history"]):
            if self.ai_brain:
                self.ai_brain.clear_history()
            msg = "Conversational memory wiped, boss. Ready for a new topic."
            self.db.log_command(raw_text, "clear_memory", "success", msg)
            return "clear_memory", msg, True

        # 5. Dashboard / Screen time queries
        if any(k in text for k in ["screen time", "dashboard", "usage stats", "show stats", "open dashboard", "show my usage"]):
            if self.on_ui_event:
                self.on_ui_event("open_dashboard", {})
            daily_stats = self.db.get_daily_screen_time()
            hours = daily_stats.get("total_hours", 0)
            mins = daily_stats.get("total_minutes", 0)
            msg = f"Opening dashboard. Today's screen time is {int(hours)} hours and {int(mins % 60)} minutes."
            self.db.log_command(raw_text, "dashboard", "success", msg)
            return "dashboard", msg, True

        # 6. Rescan apps
        if any(k in text for k in ["rescan apps", "scan apps", "refresh apps"]):
            self.app_launcher.load_or_scan(force_rescan=True)
            count = len(self.app_launcher.aliases)
            msg = f"App alias scan complete. Found {count} applications."
            self.db.log_command(raw_text, "app_rescan", "success", msg)
            return "app_rescan", msg, True

        # 7. Screenshot
        if "screenshot" in text or "capture screen" in text:
            success, msg = self.sys_cmds.take_screenshot()
            self.db.log_command(raw_text, "screenshot", "success" if success else "failed", msg)
            return "screenshot", msg, success

        # 8. Lock PC
        if "lock pc" in text or "lock computer" in text or "lock screen" in text or "lock workstation" in text:
            success, msg = self.sys_cmds.lock_workstation()
            self.db.log_command(raw_text, "lock_pc", "success" if success else "failed", msg)
            return "lock_pc", msg, success

        # Clean text by removing leading wake words or politeness prefixes for power matching
        clean_pwr = re.sub(r"^(?:hey\s+|hi\s+|ok\s+|hello\s+)?ultron\s*,?\s*", "", text).strip()
        clean_pwr = re.sub(r"^(?:can you\s+|could you\s+|please\s+|will you\s+)*", "", clean_pwr).strip()

        # 8.1 Cancel / Abort Shutdown
        cancel_shutdown_exact = {
            "cancel shutdown", "abort shutdown", "stop shutdown",
            "cancel shut down", "abort shut down", "stop shut down"
        }
        if (clean_pwr in cancel_shutdown_exact or text in cancel_shutdown_exact or
                bool(re.search(r"\b(?:cancel|abort|stop)\s+shut\s*down\b", clean_pwr))):
            success, msg = self.sys_cmds.cancel_shutdown()
            self.db.log_command(raw_text, "cancel_shutdown", "success" if success else "failed", msg)
            return "cancel_shutdown", msg, success

        # 8.2 Sleep PC / Go to sleep ("ultron go to sleep", "sleep", "sleep my pc", "put computer to sleep")
        sleep_exact = {
            "go to sleep", "sleep", "sleep pc", "sleep my pc", "sleep the pc", "sleep computer",
            "sleep my computer", "sleep mode", "enter sleep mode", "go to sleep mode",
            "suspend", "suspend pc", "pc sleep", "system sleep", "take a nap"
        }
        if (clean_pwr in sleep_exact or text in sleep_exact or
                bool(re.search(r"\b(?:go\s+to\s+sleep|enter\s+sleep(?:\s+mode)?|put\s+(?:the\s+|my\s+)?(?:pc|computer|system|workstation|laptop)\s+to\s+sleep|sleep\s+(?:the\s+|my\s+)?(?:pc|computer|system|workstation|laptop))\b", clean_pwr))):
            msg = "Entering sleep mode. Goodnight, boss."
            self.db.log_command(raw_text, "sleep", "success", msg)
            return "sleep", msg, True

        # 8.3 Shutdown PC ("ultron shutdown", "shut down my pc", "turn off computer", "power off")
        shutdown_exact = {
            "shutdown", "shut down", "power off", "power down",
            "turn off pc", "turn off the pc", "turn off my pc",
            "turn off computer", "turn off my computer", "turn off the computer",
            "turn off system", "turn off machine",
            "shutdown pc", "shut down pc", "shutdown my pc", "shut down my pc", "shutdown the pc", "shut down the pc",
            "shutdown computer", "shut down computer", "shutdown my computer", "shut down my computer",
            "power off pc", "power off my pc", "power off computer", "power off the pc",
            "power down pc", "power down my pc", "power down computer"
        }
        if (clean_pwr in shutdown_exact or text in shutdown_exact or
                bool(re.search(r"\b(?:shut\s*down|power\s*off|power\s*down|turn\s+off)\s+(?:the\s+|my\s+)?(?:pc|computer|system|machine|workstation|laptop)\b", clean_pwr)) or
                bool(re.match(r"^(?:shut\s*down|power\s*off|power\s*down)$", clean_pwr))):
            msg = "Shutting down the system. Goodbye, boss."
            self.db.log_command(raw_text, "shutdown", "success", msg)
            return "shutdown", msg, True

        # 8.4 Restart PC / Reboot ("ultron restart", "reboot my pc", "restart the computer")
        restart_exact = {
            "restart", "reboot", "restart pc", "reboot pc",
            "restart my pc", "reboot my pc", "restart the pc", "reboot the pc",
            "restart computer", "reboot computer", "restart my computer", "reboot my computer",
            "restart the computer", "reboot the computer",
            "restart system", "reboot system", "system restart", "system reboot"
        }
        if (clean_pwr in restart_exact or text in restart_exact or
                bool(re.search(r"\b(?:restart|reboot)\s+(?:the\s+|my\s+)?(?:pc|computer|system|machine|workstation|laptop)\b", clean_pwr)) or
                bool(re.match(r"^(?:restart|reboot)$", clean_pwr))):
            msg = "Restarting the system. I will be back shortly, boss."
            self.db.log_command(raw_text, "restart", "success", msg)
            return "restart", msg, True

        # 9. Show desktop
        if "show desktop" in text or "minimize all" in text or "minimize windows" in text:
            success, msg = self.sys_cmds.show_desktop()
            self.db.log_command(raw_text, "show_desktop", "success", msg)
            return "show_desktop", msg, success

        # 10. Volume controls
        if any(k in text for k in ["volume", "sound", "mute", "unmute"]):
            success, msg = self.sys_cmds.handle_volume(text)
            self.db.log_command(raw_text, "volume", "success" if success else "failed", msg)
            return "volume", msg, success

        # 11. Media controls
        if any(k in text for k in ["play music", "pause music", "next track", "previous track", "skip song", "pause", "resume"]):
            success, msg = self.sys_cmds.handle_media(text)
            self.db.log_command(raw_text, "media", "success" if success else "failed", msg)
            return "media", msg, success

        # 12. Time / Date / Status
        if any(k in text for k in ["what time", "current time", "time now"]):
            success, msg = self.sys_cmds.get_time()
            self.db.log_command(raw_text, "time", "success", msg)
            return "time", msg, success

        if any(k in text for k in ["what date", "today's date", "what day is today", "what day"]):
            success, msg = self.sys_cmds.get_date()
            self.db.log_command(raw_text, "date", "success", msg)
            return "date", msg, success

        if any(k in text for k in ["system status", "system info", "cpu usage", "battery"]):
            success, msg = self.sys_cmds.get_system_status()
            self.db.log_command(raw_text, "system_status", "success", msg)
            return "system_status", msg, success

        # 13. YouTube and Web Search Queries
        # e.g. "search aarush bola on youtube", "search python on google", "google quantum computing"
        yt_search_patterns = [
            r"^(?:can you\s+|could you\s+|please\s+)?search\s+(.+?)\s+(?:on|in)\s+youtube(?:\s+for me|\s+please)?$",
            r"^(?:can you\s+|could you\s+|please\s+)?search\s+youtube\s+(?:for\s+)?(.+?)(?:\s+for me|\s+please)?$",
            r"^(?:can you\s+|could you\s+|please\s+)?(?:play|find)\s+(.+?)\s+(?:on|in)\s+youtube(?:\s+for me|\s+please)?$"
        ]
        for pat in yt_search_patterns:
            m = re.match(pat, text)
            if m:
                query = m.group(1).strip()
                search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
                success, msg = self.website_opener.open_url(search_url, simulate_typing=False)
                resp_msg = f"Searching for {query} on YouTube"
                self.db.log_command(raw_text, "search_youtube", "success" if success else "failed", f"{msg} ({search_url})")
                return "search_youtube", resp_msg, success

        google_search_patterns = [
            r"^(?:can you\s+|could you\s+|please\s+)?search\s+(.+?)\s+(?:on|in)\s+(?:google|chrome|web|the web|the internet)(?:\s+for me|\s+please)?$",
            r"^(?:can you\s+|could you\s+|please\s+)?search\s+google\s+(?:for\s+)?(.+?)(?:\s+for me|\s+please)?$",
            r"^(?:can you\s+|could you\s+|please\s+)?google\s+(.+?)(?:\s+for me|\s+please)?$",
            r"^(?:can you\s+|could you\s+|please\s+)?search\s+(?:the\s+web\s+|the\s+internet\s+)?for\s+(.+?)(?:\s+for me|\s+please)?$"
        ]
        for pat in google_search_patterns:
            m = re.match(pat, text)
            if m:
                query = m.group(1).strip()
                search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
                success, msg = self.website_opener.open_url(search_url, simulate_typing=False)
                resp_msg = f"Searching for {query} on Google"
                self.db.log_command(raw_text, "search_google", "success" if success else "failed", f"{msg} ({search_url})")
                return "search_google", resp_msg, success

        # 14. Website / URL detection
        is_url, norm_url = self.website_opener.normalize_spoken_url(text)
        if is_url:
            success, msg = self.website_opener.open_url(norm_url, simulate_typing=False)
            self.db.log_command(raw_text, "open_url", "success" if success else "failed", f"{msg} ({norm_url})")
            return "open_url", f"Opening {norm_url}", success

        # 14.5 File Explorer, Drive Roots, and Explicit Folder Navigation
        # e.g. "open file explorer", "open d drive", "open social internship folder", "access social internship"
        if text in [
            "file explorer", "explorer", "my files", "open file explorer", "open explorer",
            "open my files", "open files", "launch file explorer", "show file explorer"
        ]:
            success, msg, path = self.folder_manager.find_and_open("file explorer", is_cancelled=is_cancelled)
            self.db.log_command(raw_text, "open_folder", "success" if success else "failed", msg)
            return "open_folder", msg, success

        if any(text == p for p in ["open d drive", "open drive d", "open d:", "access d drive", "access drive d", "d drive", "open my d drive"]):
            success, msg, path = self.folder_manager.find_and_open("d drive", is_cancelled=is_cancelled)
            self.db.log_command(raw_text, "open_folder", "success" if success else "failed", msg)
            return "open_folder", msg, success

        if any(text == p for p in ["open c drive", "open drive c", "open c:", "access c drive", "access drive c", "c drive", "open my c drive"]):
            success, msg, path = self.folder_manager.find_and_open("c drive", is_cancelled=is_cancelled)
            self.db.log_command(raw_text, "open_folder", "success" if success else "failed", msg)
            return "open_folder", msg, success

        # 14.6 Explicit File Opening & Media Playback (Videos strictly in VLC, Documents in Default Handler)
        # e.g. "open bigg boss video", "play breaking bad episode 1", "open in vlc bigg boss", "open pitch deck ppt", "open report.pdf"
        file_prefix = r"^(?:can you\s+|could you\s+|please\s+|will you\s+)*"
        file_explicit_patterns = [
            # Play command (e.g. "play breaking bad episode 1", "play bigg boss", "play sample.mp4")
            file_prefix + r"play\s+(?:my\s+|the\s+)?(.+?)(?:\s+(?:in|on|with)\s+vlc)?(?:\s+(?:for me|please))?$",
            # VLC specific commands (e.g. "open bigg boss in vlc", "open in vlc bigg boss")
            file_prefix + r"(?:open|launch|start|access|show|find)\s+(?:my\s+|the\s+)?(.+?)\s+(?:in|on|with)\s+vlc(?:\s+(?:for me|please))?$",
            file_prefix + r"(?:open|launch|start|access|show|find)\s+(?:in|on|with)\s+vlc\s+(?:my\s+|the\s+)?(.+?)(?:\s+(?:for me|please))?$",
            # Explicit video/movie patterns
            file_prefix + r"(?:open|launch|start|access|show|view|find)\s+(?:my\s+|the\s+)?(.+?)\s+(?:video|movie|film|clip)(?:\s+(?:for me|please))?$",
            file_prefix + r"(?:open|launch|start|access|show|view|find)\s+(?:my\s+|the\s+)?(?:video|movie|film|clip)\s+(?:named\s+|called\s+)?(.+?)(?:\s+(?:for me|please))?$",
            # Explicit document patterns (pdf, ppt, doc, excel, sheet, notes, document, presentation)
            file_prefix + r"(?:open|launch|start|access|show|view|find)\s+(?:my\s+|the\s+)?(.+?)\s+(?:pdf|ppt|pptx|doc|docx|excel|sheet|spreadsheet|document|presentation|slides|notes)(?:\s+(?:for me|please))?$",
            file_prefix + r"(?:open|launch|start|access|show|view|find)\s+(?:my\s+|the\s+)?(?:pdf|ppt|pptx|doc|docx|excel|sheet|spreadsheet|document|presentation)\s+(?:named\s+|called\s+)?(.+?)(?:\s+(?:for me|please))?$",
            # Explicit file patterns
            file_prefix + r"(?:open|launch|start|access|show|view|find)\s+(?:my\s+|the\s+)?(.+?)\s+file(?:\s+(?:for me|please))?$",
            file_prefix + r"(?:open|launch|start|access|show|view|find)\s+(?:my\s+|the\s+)?file\s+(?:named\s+|called\s+)?(.+?)(?:\s+(?:for me|please))?$",
            # Direct filename with extension (e.g. "open report.pdf", "play movie.mp4")
            file_prefix + r"(?:open|play|launch|start|access|show|view|find)\s+(?:my\s+|the\s+)?(.+?\.(?:mp4|mkv|avi|mov|wmv|flv|webm|m4v|3gp|ts|pdf|pptx?|docx?|xlsx?|csv|txt|png|jpg|jpeg))(?:\s+(?:for me|please))?$"
        ]

        for pat in file_explicit_patterns:
            m = re.match(pat, text)
            if m:
                target_f = m.group(1).strip()
                target_f = re.sub(r"\s+(?:for me|please)$", "", target_f).strip()
                if target_f:
                    success, f_msg, path = self.file_manager.find_and_open(raw_text, is_cancelled=is_cancelled)
                    self.db.log_command(raw_text, "open_file", "success" if success else "failed", f_msg)
                    return "open_file", f_msg, success

        folder_explicit_patterns = [
            # "open/access/show/view/find [my/the] (.+) folder/directory/dir [in/on drive X]"
            r"^(?:can you\s+|could you\s+|please\s+)?(?:open|access|show|view|find|go to|explore)\s+(?:my\s+|the\s+)?(.+?)\s+(?:folder|directory|dir)(?:\s+(?:in|on)\s+(?:drive\s+[a-zA-Z]|[a-zA-Z]\s+drive|[a-zA-Z]:?))?(?:\s+(?:for me|please))?$",
            # "open/access/show/view/find [my/the] folder/directory/dir [named/called] (.+)"
            r"^(?:can you\s+|could you\s+|please\s+)?(?:open|access|show|view|find|go to|explore)\s+(?:my\s+|the\s+)?(?:folder|directory|dir)\s+(?:named\s+|called\s+)?(.+?)(?:\s+(?:for me|please))?$",
            # "access [my/the] (.+) [in/on drive X]"
            r"^(?:can you\s+|could you\s+|please\s+)?access\s+(?:my\s+|the\s+)?(.+?)(?:\s+(?:in|on)\s+(?:drive\s+[a-zA-Z]|[a-zA-Z]\s+drive|[a-zA-Z]:?))?(?:\s+(?:for me|please))?$"
        ]
        for pat in folder_explicit_patterns:
            m = re.match(pat, text)
            if m:
                target_folder = m.group(1).strip()
                target_folder = re.sub(r"\s+(?:for me|please)$", "", target_folder).strip()
                if target_folder:
                    f_path, _ = self.folder_manager.find_folder(target_folder, is_cancelled=is_cancelled)
                    if f_path:
                        success, msg, path = self.folder_manager.find_and_open(target_folder, is_cancelled=is_cancelled)
                        self.db.log_command(raw_text, "open_folder", "success" if success else "failed", msg)
                        return "open_folder", msg, success
                    else:
                        # Check if target is a file instead
                        fl_path, _, _ = self.file_manager.find_file(target_folder, is_cancelled=is_cancelled)
                        if fl_path:
                            success, file_msg, _ = self.file_manager.find_and_open(target_folder, is_cancelled=is_cancelled)
                            self.db.log_command(raw_text, "open_file", "success" if success else "failed", file_msg)
                            return "open_file", file_msg, success
                        # Neither found, call folder manager to produce standard not found response
                        success, msg, path = self.folder_manager.find_and_open(target_folder, is_cancelled=is_cancelled)
                        self.db.log_command(raw_text, "open_folder", "success" if success else "failed", msg)
                        return "open_folder", msg, success

        # 15. Explicit App Launching Commands
        # e.g. "open blender", "launch spotify", "run notepad"
        open_pattern = r"^(?:can you\s+|could you\s+|please\s+|will you\s+)?(?:open|launch|start|run|bring up)(?:\s+up)?\s+(.+?)(?:\s+(?:for me|please))?$"
        open_match = re.match(open_pattern, text)
        if open_match:
            app_target = open_match.group(1).strip()
            app_target = re.sub(r"\s+(?:for me|please)$", "", app_target).strip()

            # Double check if target is a website
            is_u, u = self.website_opener.normalize_spoken_url(app_target)
            if is_u:
                success, msg = self.website_opener.open_url(u, simulate_typing=False)
                self.db.log_command(raw_text, "open_url", "success" if success else "failed", msg)
                return "open_url", f"Opening {u}", success

            # Attempt app launch
            success, msg = self.app_launcher.launch(app_target)
            if success:
                self.db.log_command(raw_text, "launch_app", "success", msg)
                return "launch_app", msg, True

            # If app launch failed, check if target is a folder on D: or C: drive
            folder_path, _ = self.folder_manager.find_folder(app_target, is_cancelled=is_cancelled)
            if folder_path:
                success, f_msg, _ = self.folder_manager.find_and_open(app_target, is_cancelled=is_cancelled)
                self.db.log_command(raw_text, "open_folder", "success" if success else "failed", f_msg)
                return "open_folder", f_msg, success

            # If app and folder failed, check if target is a file (video in VLC, PDF, PPT, DOC, etc.)
            file_path, _, _ = self.file_manager.find_file(app_target, is_cancelled=is_cancelled)
            if file_path:
                success, file_msg, _ = self.file_manager.find_and_open(app_target, is_cancelled=is_cancelled)
                self.db.log_command(raw_text, "open_file", "success" if success else "failed", file_msg)
                return "open_file", file_msg, success

            # If app launch failed, but user asked for a website / browser target (e.g. 'cricbuzz' or 'flipkart')
            if any(k in raw_text.lower() for k in ["website", "site", "web", "in chrome", "on chrome", "browser"]):
                clean_target = re.sub(r"[^a-zA-Z0-9\-]", "", app_target)
                if clean_target and clean_target not in ["chrome", "browser", "edge", "firefox"]:
                    fallback_url = f"https://www.{clean_target}.com"
                    success, msg = self.website_opener.open_url(fallback_url, simulate_typing=False)
                    if success:
                        self.db.log_command(raw_text, "open_url", "success", msg)
                        return "open_url", f"Opening {fallback_url}", True
            # If app launch failed, but user might be asking a question like "open up about your past", fall through to AI

        # 15. Check if text matches an exact app alias with high confidence (e.g. user just said "calculator")
        match = self.app_launcher.find_app(text, threshold=85)
        if match and len(text.split()) <= 2:
            success, msg = self.app_launcher.launch(match[0])
            if success:
                self.db.log_command(raw_text, "launch_app", "success", msg)
                return "launch_app", msg, True

        # 16. FULL AI CONVERSATION BRAIN
        # Handles ANY open-ended question, conversation, explanation, math, philosophy, jokes, etc.
        if self.ai_brain:
            if is_cancelled and is_cancelled():
                return "cancelled", "", False
            reply, action_meta = self.ai_brain.chat(raw_text)
            if is_cancelled and is_cancelled():
                return "cancelled", "", False
            if action_meta:
                act = action_meta.get("action")
                if act == "screenshot":
                    self.sys_cmds.take_screenshot()
                elif act == "lock_pc":
                    self.sys_cmds.lock_workstation()
                elif act == "volume":
                    self.sys_cmds.handle_volume("mute")
                elif act == "shutdown":
                    return "shutdown", "Shutting down the system. Goodbye, boss.", True
                elif act == "restart":
                    return "restart", "Restarting the system. I will be back shortly, boss.", True
                elif act == "sleep":
                    return "sleep", "Entering sleep mode. Goodnight, boss.", True
            self.db.log_command(raw_text, "ai_chat", "success", reply)
            return "ai_chat", reply, True

        # Unrecognized fallback
        fallback_msg = f"I heard '{raw_text}', but could not determine an action."
        self.db.log_command(raw_text, "unknown", "failed", fallback_msg)
        return "unknown", fallback_msg, False
