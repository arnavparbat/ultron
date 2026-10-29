"""
Ultron Power Commands & Voice Wake System Test Suite
Verifies Sleep, Shutdown, and Restart parsing, wake phrase extraction,
and SystemCommands functionality without executing actual OS power cuts.
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add ultron-backend to sys.path
sys.path.insert(0, str(Path(__file__).parent / "ultron-backend"))

from command_parser import CommandParser
from database import Database
from app_launcher import AppLauncher
from website_opener import WebsiteOpener
from system_commands import SystemCommands
from wake_detector import WakeDetector
from ai_brain import AIBrain

def test_power_system():
    print("=" * 60)
    print("TESTING ULTRON POWER MANAGEMENT & WAKE WORD SYSTEM")
    print("=" * 60)

    db = MagicMock()
    app_launcher = MagicMock()
    website_opener = MagicMock()
    sys_cmds = SystemCommands()
    brain = AIBrain()
    parser = CommandParser(db, app_launcher, website_opener, sys_cmds, ai_brain=brain)

    # 1. Test CommandParser Sleep phrases
    print("\n[1] Testing Sleep Command Variations...")
    sleep_phrases = [
        "ultron go to sleep",
        "hey ultron go to sleep",
        "go to sleep",
        "ultron sleep",
        "sleep",
        "sleep pc",
        "sleep my pc",
        "put pc to sleep",
        "put my pc to sleep",
        "enter sleep mode",
        "go to sleep mode",
        "suspend pc"
    ]
    for p in sleep_phrases:
        cmd_type, msg, success = parser.parse_and_execute(p)
        print(f"  Phrase: '{p}' -> Type: {cmd_type} | Message: {msg}")
        assert cmd_type == "sleep", f"Expected 'sleep', got '{cmd_type}' for '{p}'"
        assert success is True
        assert "sleep" in msg.lower()

    # 2. Test CommandParser Shutdown phrases
    print("\n[2] Testing Shutdown Command Variations...")
    shutdown_phrases = [
        "ultron shutdown",
        "hey ultron shutdown",
        "shutdown",
        "shut down",
        "shutdown pc",
        "shut down pc",
        "shutdown my pc",
        "shut down my pc",
        "turn off pc",
        "turn off my pc",
        "turn off computer",
        "power off",
        "power down pc"
    ]
    for p in shutdown_phrases:
        cmd_type, msg, success = parser.parse_and_execute(p)
        print(f"  Phrase: '{p}' -> Type: {cmd_type} | Message: {msg}")
        assert cmd_type == "shutdown", f"Expected 'shutdown', got '{cmd_type}' for '{p}'"
        assert success is True
        assert "shutting down" in msg.lower()

    # 3. Test CommandParser Restart phrases
    print("\n[3] Testing Restart Command Variations...")
    restart_phrases = [
        "ultron restart",
        "hey ultron restart",
        "restart",
        "reboot",
        "restart pc",
        "reboot pc",
        "restart my pc",
        "reboot my pc",
        "restart computer",
        "reboot computer",
        "restart the computer"
    ]
    for p in restart_phrases:
        cmd_type, msg, success = parser.parse_and_execute(p)
        print(f"  Phrase: '{p}' -> Type: {cmd_type} | Message: {msg}")
        assert cmd_type == "restart", f"Expected 'restart', got '{cmd_type}' for '{p}'"
        assert success is True
        assert "restarting" in msg.lower()

    # 4. Test WakeDetector Inline Extraction
    print("\n[4] Testing WakeDetector Wake Phrase & Inline Extraction...")
    wake_detector = WakeDetector(
        on_wake=lambda *a: None,
        on_command=lambda *a: None
    )

    wake_test_cases = [
        ("ultron go to sleep", True, "go to sleep"),
        ("hey ultron go to sleep", True, "go to sleep"),
        ("ultron shutdown", True, "shutdown"),
        ("hey ultron shutdown", True, "shutdown"),
        ("ultron shut down", True, "shut down"),
        ("ultron restart", True, "restart"),
        ("hey ultron restart", True, "restart"),
        ("altron go to sleep", True, "go to sleep"),
        ("go to sleep ultron", True, "go to sleep"),
        ("shutdown ultron", True, "shutdown"),
        ("restart ultron", True, "restart"),
        ("hey ultron", True, "")
    ]

    for speech_input, expected_match, expected_inline in wake_test_cases:
        matched, inline = wake_detector.check_wake_phrase(speech_input)
        print(f"  Heard: '{speech_input}' -> Matched: {matched} | Inline: '{inline}'")
        assert matched == expected_match, f"Failed match for '{speech_input}'"
        assert inline.lower() == expected_inline.lower(), f"Expected inline '{expected_inline}', got '{inline}' for '{speech_input}'"

    # 5. Test AI Brain Action Extraction Fallback
    print("\n[5] Testing AI Brain Action Extraction Fallback...")
    act_sleep = brain._extract_action("could you put my pc to sleep", "")
    print(f"  AI extract 'could you put my pc to sleep' -> {act_sleep}")
    assert act_sleep and act_sleep.get("action") == "sleep"

    act_shutdown = brain._extract_action("please turn off my pc", "")
    print(f"  AI extract 'please turn off my pc' -> {act_shutdown}")
    assert act_shutdown and act_shutdown.get("action") == "shutdown"

    act_restart = brain._extract_action("can you reboot my pc", "")
    print(f"  AI extract 'can you reboot my pc' -> {act_restart}")
    assert act_restart and act_restart.get("action") == "restart"

    # 6. Test Cancel Shutdown
    print("\n[6] Testing Cancel Shutdown Command...")
    with patch("subprocess.Popen") as mock_popen:
        cmd_type, msg, success = parser.parse_and_execute("cancel shutdown")
        print(f"  Query: 'cancel shutdown' -> Type: {cmd_type} | Message: {msg}")
        assert cmd_type == "cancel_shutdown"
        assert success is True
        mock_popen.assert_called_once_with("shutdown /a", shell=True)

    print("\n" + "=" * 60)
    print("ALL POWER MANAGEMENT & WAKE WORD TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_power_system()
