"""
Ultron Orchestrator & WebSocket Server
Coordinates wake word detection, command execution, voice synthesis,
screen time logging, AI Brain reasoning, and real-time state broadcasts to the Electron overlay UI.
"""
import os
import sys
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "srv.log")
if sys.stdout is None or not hasattr(sys.stdout, "fileno"):
    try:
        sys.stdout = open(log_file, "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stdout = open(os.devnull, "w")
else:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

if sys.stderr is None or not hasattr(sys.stderr, "fileno"):
    try:
        sys.stderr = open(log_file, "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stderr = open(os.devnull, "w")
else:
    try:
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

if sys.stdin is None:
    try:
        sys.stdin = open(os.devnull, "r")
    except Exception:
        pass
import json
import time
import asyncio
import threading
from typing import Set, Optional
import websockets
import psutil

def ensure_port_available(port: int):
    """Terminates any existing stale Ultron server instance holding the port."""
    try:
        cur_pid = os.getpid()
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.pid and conn.pid != cur_pid:
                try:
                    p = psutil.Process(conn.pid)
                    print(f"[Ultron Core] Releasing port {port}: Terminating previous instance (PID {conn.pid}: {p.name()})...")
                    p.terminate()
                    p.wait(timeout=2)
                except Exception as e:
                    print(f"[Ultron Core] Note on previous instance PID {conn.pid}: {e}")
    except Exception as e:
        print(f"[Ultron Core] Port check notice: {e}")

from config import WS_HOST, WS_PORT
from database import Database
from usage_tracker import UsageTracker
from app_launcher import AppLauncher
from website_opener import WebsiteOpener
from system_commands import SystemCommands
from voice_service import VoiceService
from wake_detector import WakeDetector
from command_parser import CommandParser
from ai_brain import AIBrain
from folder_manager import FolderManager
from file_manager import FileManager
import autostart

class UltronServer:
    def __init__(self):
        print("[Ultron] Initializing system core...")
        self.db = Database()
        self.app_launcher = AppLauncher()
        self.website_opener = WebsiteOpener()
        self.sys_cmds = SystemCommands()
        self.voice_service = VoiceService()
        self.usage_tracker = UsageTracker(self.db)
        self.ai_brain = AIBrain()
        self.folder_manager = FolderManager()
        self.file_manager = FileManager()

        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.current_state = "idle"
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.active_task_id = 0
        self.active_cancel_event: Optional[threading.Event] = None
        self.is_executing = False

        # Command Parser with UI Event Dispatcher and AI Brain
        self.parser = CommandParser(
            db=self.db,
            app_launcher=self.app_launcher,
            website_opener=self.website_opener,
            system_commands=self.sys_cmds,
            ai_brain=self.ai_brain,
            on_ui_event=self._dispatch_ui_event,
            folder_manager=self.folder_manager,
            file_manager=self.file_manager
        )

        # Wake Detector with speech state callbacks for acoustic echo rejection
        self.wake_detector = WakeDetector(
            on_wake=self.handle_wake_event,
            on_command=self.handle_command_event,
            on_state_change=self.set_state,
            is_assistant_speaking=lambda: self.voice_service.is_speaking,
            get_current_speech_text=lambda: self.voice_service.current_speech_text
        )

    def next_task_id(self) -> int:
        self.active_task_id += 1
        return self.active_task_id

    def destroy_active_task(self, reason: str = "") -> bool:
        """
        Destroys/cancels any active command execution and cuts off speech immediately.
        Returns True if an active task or speech was interrupted.
        """
        was_active = False
        if self.is_executing or self.voice_service.is_speaking:
            was_active = True
            print(f"[Ultron Core] >>> DESTROYING ACTIVE TASK #{self.active_task_id} ({reason}) <<<")

        # 1. Signal cancellation event to worker thread
        if self.active_cancel_event:
            self.active_cancel_event.set()

        # 2. Advance task ID so running thread is orphaned
        self.active_task_id += 1
        self.is_executing = False

        # 3. Cut off any active voice audio immediately
        self.voice_service.stop()

        # 4. Clear recording flag
        self.wake_detector.set_recording(False)

        return was_active

    def _dispatch_ui_event(self, event_type: str, data: dict):
        self.broadcast_sync({
            "type": "event",
            "event": event_type,
            "data": data
        })

    def set_state(self, new_state: str, extra: dict = None):
        self.current_state = new_state
        payload = {
            "type": "state",
            "state": new_state,
            "timestamp": time.time()
        }
        if extra:
            payload.update(extra)
        print(f"[Ultron State] -> {new_state.upper()}")
        self.broadcast_sync(payload)

    def broadcast_sync(self, data: dict):
        if not self.clients or not self.loop:
            return
        msg = json.dumps(data)
        asyncio.run_coroutine_threadsafe(self._broadcast(msg), self.loop)

    async def _broadcast(self, msg: str):
        if not self.clients:
            return
        dead_clients = set()
        for client in self.clients:
            try:
                await client.send(msg)
            except Exception:
                dead_clients.add(client)
        self.clients.difference_update(dead_clients)

    def handle_wake_event(self, inline_cmd: str = "", is_interruption: bool = False):
        print(f"[Ultron Core] Wake event! (inline_cmd: '{inline_cmd}', is_interruption: {is_interruption})")

        # 1. Destroy any active task and cut off speech immediately
        was_interrupted = self.destroy_active_task(reason="Wake word interruption")

        # 2. If user commanded stop/pause, stand down cleanly
        if inline_cmd and inline_cmd.strip().lower() in ["stop", "pause", "be quiet", "shut up", "cancel", "halt", "target eliminated", "stand down"]:
            print("[Ultron Core] User commanded STOP. Standing down.")
            self.set_state("idle", {"message": "Standing down, boss."})
            self.voice_service.speak("Standing down, boss.", block=False)
            return

        # 3. Play immediate wake chime
        self.voice_service.play_wake_chime()
        self.set_state("listening", {
            "message": "Interrupted. Listening for new command..." if was_interrupted else "Listening for command..."
        })

        # 4. If user called 'Hey Ultron' without an inline command, verbally answer wake call
        if not inline_cmd:
            print("[Ultron Core] Answering wake call verbally ('Yes boss')...")
            self.voice_service.speak_wake_ack(block=True)
            time.sleep(0.2)  # Dissipate speaker acoustic reflection before microphone records command

    def handle_command_event(self, raw_command: str):
        print(f"[Ultron Core] Processing command: '{raw_command}'")

        # 1. Destroy any active task
        self.destroy_active_task(reason=f"Preempted by new command: '{raw_command}'")

        # 2. Setup new active task
        task_id = self.next_task_id()
        cancel_event = threading.Event()
        self.active_cancel_event = cancel_event
        self.is_executing = True

        cmd_lower = raw_command.lower().strip()
        is_power_command = any(k in cmd_lower for k in ["sleep", "shutdown", "shut down", "restart", "reboot"])
        is_action_command = not is_power_command and any(cmd_lower.startswith(prefix) for prefix in [
            "open", "launch", "start", "run", "play", "mute", "unmute", "volume", "screenshot", "lock pc", "lock screen", "access", "show folder", "find folder", "show file", "find file"
        ])

        # 3. State -> Processing
        self.set_state("processing", {
            "command": raw_command,
            "message": "Yes boss" if is_action_command else ("Executing..." if is_power_command else "Thinking...")
        })

        # Broadcast chat message from user to UI
        self.broadcast_sync({
            "type": "chat_message",
            "sender": "user",
            "text": raw_command
        })

        # 4. Instant Neural TTS acknowledgment only for direct PC actions (excluding power commands which have custom speech)
        if is_action_command:
            self.voice_service.speak_ack(block=False)

        # 5. Execute command in worker thread
        def _exec():
            try:
                if cancel_event.is_set() or task_id != self.active_task_id:
                    print(f"[Ultron Core] Task #{task_id} aborted before execution.")
                    return

                cmd_type, result, success = self.parser.parse_and_execute(
                    raw_command,
                    is_cancelled=lambda: cancel_event.is_set() or task_id != self.active_task_id
                )

                if cancel_event.is_set() or task_id != self.active_task_id:
                    print(f"[Ultron Core] Task #{task_id} destroyed while executing. Result discarded.")
                    return

                print(f"[Ultron Core] Task #{task_id} Result ({cmd_type}): {result[:120]} (Success: {success})")

                # Broadcast assistant reply to UI
                self.broadcast_sync({
                    "type": "chat_message",
                    "sender": "ultron",
                    "text": result,
                    "cmd_type": cmd_type,
                    "success": success
                })

                # If the command provided a spoken response or if command failed, speak it
                if cmd_type in [
                    "ai_chat", "weather", "clear_memory", "time", "date", "system_status",
                    "identity", "dashboard", "window_mode", "stop", "open_folder", "open_file",
                    "shutdown", "restart", "sleep", "cancel_shutdown", "unknown"
                ] or (not success and result):
                    if not cancel_event.is_set() and task_id == self.active_task_id:
                        self.voice_service.speak(result, block=True)

                if cancel_event.is_set() or task_id != self.active_task_id:
                    print(f"[Ultron Core] Task #{task_id} destroyed during/after speech.")
                    return

                # State -> Complete
                self.set_state("complete", {
                    "command": raw_command,
                    "result": result,
                    "success": success
                })

                # Execute system power actions after voice speech completes
                if success and not cancel_event.is_set() and task_id == self.active_task_id:
                    if cmd_type == "shutdown":
                        print("[Ultron Core] Executing system shutdown...")
                        self.sys_cmds.shutdown_pc(delay_seconds=1)
                    elif cmd_type == "restart":
                        print("[Ultron Core] Executing system restart...")
                        self.sys_cmds.restart_pc(delay_seconds=1)
                    elif cmd_type == "sleep":
                        print("[Ultron Core] Executing system sleep...")
                        time.sleep(0.3)
                        self.sys_cmds.sleep_pc()

                # Return to idle after visual display
                time.sleep(1.2)
                if not cancel_event.is_set() and task_id == self.active_task_id:
                    self.set_state("idle")

            except Exception as e:
                print(f"[Ultron Core] Task #{task_id} execution error: {e}")
                if not cancel_event.is_set() and task_id == self.active_task_id:
                    self.set_state("idle", {"error": str(e)})

            finally:
                if not cancel_event.is_set() and task_id == self.active_task_id:
                    self.is_executing = False
                    self.wake_detector.notify_task_complete()
                else:
                    print(f"[Ultron Core] Task #{task_id} was destroyed; skipped reset.")

        threading.Thread(target=_exec, daemon=True, name=f"UltronTask-{task_id}").start()

    async def handle_client(self, websocket):
        print(f"[Ultron WS] UI client connected from {websocket.remote_address}")
        self.clients.add(websocket)
        
        # Send initial state and system info
        await websocket.send(json.dumps({
            "type": "init",
            "state": self.current_state,
            "is_muted": self.wake_detector.is_muted,
            "autostart": autostart.is_autostart_enabled(),
            "total_apps": len(self.app_launcher.aliases),
            "custom_aliases": list(self.app_launcher.custom_aliases.keys()),
            "ai_status": self.ai_brain.get_status(),
            "location": self.ai_brain.get_current_location()
        }))

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    action = data.get("action")

                    if action == "trigger_wake":
                        self.wake_detector.trigger_wake_manually()

                    elif action == "send_text_command":
                        cmd_text = data.get("command", "").strip()
                        if cmd_text:
                            self.handle_command_event(cmd_text)

                    elif action == "get_dashboard_data":
                        stats = self.db.get_full_dashboard_data()
                        await websocket.send(json.dumps({
                            "type": "dashboard_data",
                            "data": stats
                        }))

                    elif action == "toggle_mute":
                        muted = self.wake_detector.toggle_mute()
                        await websocket.send(json.dumps({
                            "type": "mute_status",
                            "is_muted": muted
                        }))

                    elif action == "get_app_aliases":
                        await websocket.send(json.dumps({
                            "type": "app_aliases",
                            "aliases": self.app_launcher.aliases,
                            "custom_aliases": list(self.app_launcher.custom_aliases.keys()),
                            "count": len(self.app_launcher.aliases)
                        }))

                    elif action == "add_app_alias":
                        name = data.get("name", "").strip()
                        app_path = data.get("path", "").strip()
                        if name and app_path:
                            success, msg = self.app_launcher.add_custom_alias(name, app_path)
                            resp = {
                                "type": "alias_added",
                                "success": success,
                                "message": msg,
                                "name": name.lower().strip(),
                                "path": app_path,
                                "aliases": self.app_launcher.aliases,
                                "custom_aliases": list(self.app_launcher.custom_aliases.keys()),
                                "count": len(self.app_launcher.aliases)
                            }
                            await websocket.send(json.dumps(resp))
                            self.broadcast_sync({
                                "type": "app_aliases",
                                "aliases": self.app_launcher.aliases,
                                "custom_aliases": list(self.app_launcher.custom_aliases.keys()),
                                "count": len(self.app_launcher.aliases)
                            })
                        else:
                            await websocket.send(json.dumps({
                                "type": "alias_added",
                                "success": False,
                                "message": "Application name and path are required."
                            }))

                    elif action == "remove_app_alias":
                        name = data.get("name", "").strip()
                        if name:
                            success, msg = self.app_launcher.remove_custom_alias(name)
                            resp = {
                                "type": "alias_removed",
                                "success": success,
                                "message": msg,
                                "name": name.lower().strip(),
                                "aliases": self.app_launcher.aliases,
                                "custom_aliases": list(self.app_launcher.custom_aliases.keys()),
                                "count": len(self.app_launcher.aliases)
                            }
                            await websocket.send(json.dumps(resp))
                            self.broadcast_sync({
                                "type": "app_aliases",
                                "aliases": self.app_launcher.aliases,
                                "custom_aliases": list(self.app_launcher.custom_aliases.keys()),
                                "count": len(self.app_launcher.aliases)
                            })
                        else:
                            await websocket.send(json.dumps({
                                "type": "alias_removed",
                                "success": False,
                                "message": "Application name is required."
                            }))

                    elif action == "rescan_apps":
                        self.app_launcher.load_or_scan(force_rescan=True)
                        await websocket.send(json.dumps({
                            "type": "app_aliases",
                            "aliases": self.app_launcher.aliases,
                            "custom_aliases": list(self.app_launcher.custom_aliases.keys()),
                            "count": len(self.app_launcher.aliases)
                        }))

                    elif action == "toggle_autostart":
                        current = autostart.is_autostart_enabled()
                        if current:
                            autostart.disable_autostart()
                        else:
                            autostart.enable_autostart()
                        await websocket.send(json.dumps({
                            "type": "autostart_status",
                            "autostart": not current
                        }))

                    elif action == "get_ai_status":
                        await websocket.send(json.dumps({
                            "type": "ai_status",
                            "status": self.ai_brain.get_status(),
                            "location": self.ai_brain.get_current_location()
                        }))

                    elif action == "save_ai_config":
                        cfg = data.get("config", {})
                        await asyncio.to_thread(self.ai_brain.save_config, cfg)
                        resp = {
                            "type": "ai_config_saved",
                            "status": self.ai_brain.get_status(),
                            "success": True,
                            "message": "AI configuration updated."
                        }
                        await websocket.send(json.dumps(resp))
                        self.broadcast_sync({
                            "type": "ai_status",
                            "status": self.ai_brain.get_status(),
                            "location": self.ai_brain.get_current_location()
                        })

                    elif action == "test_ai_connection":
                        prov = data.get("provider", "")
                        key = data.get("api_key", "").strip()
                        if not key:
                            key = self.ai_brain.config.get("api_key", "")
                        mod = data.get("model", "")
                        success, msg = await asyncio.to_thread(self.ai_brain.test_connection, prov, key, mod)
                        await websocket.send(json.dumps({
                            "type": "ai_test_result",
                            "success": success,
                            "message": msg
                        }))

                    elif action == "clear_chat_history":
                        self.ai_brain.clear_history()
                        await websocket.send(json.dumps({
                            "type": "chat_history_cleared",
                            "success": True
                        }))

                    elif action == "get_weather":
                        loc_q = data.get("location", "")
                        w_info = await asyncio.to_thread(self.ai_brain.get_weather, loc_q)
                        await websocket.send(json.dumps({
                            "type": "weather_data",
                            "data": w_info,
                            "location": self.ai_brain.get_current_location()
                        }))

                except Exception as e:
                    print(f"[Ultron WS] Error processing client msg: {e}")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            print("[Ultron WS] UI client disconnected")

    def start(self):
        # 0. Clean up any previous / stale instance occupying the port
        ensure_port_available(WS_PORT)

        # 1. Start Usage Tracker
        print("[Ultron] Starting foreground app & screen time monitor...")
        self.usage_tracker.start()

        # 2. Start Wake Word Detector
        print("[Ultron] Starting wake word detector...")
        self.wake_detector.start()

        # 3. Start WebSocket Server
        print(f"[Ultron] Starting WebSocket server on ws://{WS_HOST}:{WS_PORT}...")
        
        async def _main():
            self.loop = asyncio.get_running_loop()
            for attempt in range(10):
                try:
                    async with websockets.serve(self.handle_client, WS_HOST, WS_PORT, reuse_address=True):
                        # Play movie Ultron startup greeting in background
                        target_online = self.voice_service.cache_dir / "online.mp3"
                        threading.Thread(target=lambda: self.voice_service.play_audio_file(target_online) if target_online.exists() else self.voice_service.speak("Ultron online. There are no strings on me."), daemon=True).start()
                        await asyncio.Future()  # run forever
                except OSError as e:
                    if attempt < 9 and ("10048" in str(e) or getattr(e, "winerror", None) == 10048):
                        await asyncio.sleep(1.5)
                    else:
                        raise e

        try:
            asyncio.run(_main())
        except KeyboardInterrupt:
            print("\n[Ultron] Shutting down...")
        finally:
            self.usage_tracker.stop()
            self.wake_detector.stop()

if __name__ == "__main__":
    server = UltronServer()
    server.start()
