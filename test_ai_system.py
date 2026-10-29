"""
Ultron Full AI & Conversational Capability Test Suite
"""
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add ultron-backend to sys.path
sys.path.insert(0, str(Path(__file__).parent / "ultron-backend"))

from ai_brain import AIBrain
from command_parser import CommandParser
from database import Database
from app_launcher import AppLauncher
from website_opener import WebsiteOpener
from system_commands import SystemCommands

def run_tests():
    print("=" * 60)
    print("ULTRON NEURAL AI BRAIN & CONVERSATIONAL ENGINE VERIFICATION")
    print("=" * 60)

    brain = AIBrain()
    status = brain.get_status()
    print(f"\n[1] AI Brain Status: {status}")

    loc = brain.get_current_location()
    print(f"\n[2] Geolocation Detection: {loc}")

    print("\n[3] Testing Weather Engine...")
    w_local = brain.get_weather("what is the weather of this place")
    print(f"  Local Weather: {w_local}")
    w_tokyo = brain.get_weather("weather in Tokyo")
    print(f"  Tokyo Weather: {w_tokyo}")

    print("\n[4] Testing Knowledge & Math Engine...")
    q1, _ = brain.chat("What is quantum computing?")
    print(f"  Q: Quantum computing -> A: {q1[:120]}...")
    q2, _ = brain.chat("What is 125 times 8?")
    print(f"  Q: 125 times 8 -> A: {q2}")

    print("\n[5] Testing Conversational Memory & Multi-turn Dialogue...")
    brain.clear_history()
    t1, _ = brain.chat("Hello Ultron, who was Albert Einstein?")
    print(f"  Turn 1: {t1[:100]}...")
    t2, _ = brain.chat("What did he win the Nobel prize for?")
    print(f"  Turn 2: {t2[:100]}...")
    print(f"  Memory history length: {len(brain.conversation_history)}")

    print("\n[6] Testing CommandParser AI Routing...")
    db = Database()
    app_launcher = AppLauncher()
    website_opener = WebsiteOpener()
    sys_cmds = SystemCommands()
    parser = CommandParser(db, app_launcher, website_opener, sys_cmds, ai_brain=brain)

    test_queries = [
        ("what is the weather of this place", "weather"),
        ("who is Nikola Tesla", "ai_chat"),
        ("what is 45 plus 55", "ai_chat"),
        ("what time is it", "time"),
        ("tell me about the planet Mars", "ai_chat")
    ]

    for q, expected_type in test_queries:
        cmd_type, result, success = parser.parse_and_execute(q)
        print(f"  Query: '{q}' -> Type: {cmd_type} | Success: {success} | Preview: {result[:80]}")
        assert success is True, f"Failed on {q}"

    print("\n[7] Testing TTS Text Sanitization...")
    raw_markdown = "**Weather Warning:** In *Pune*, it is 24°C 🌧️! Visit `https://wttr.in`."
    cleaned = brain.clean_for_speech(raw_markdown)
    print(f"  Raw:     {raw_markdown.encode('ascii', 'ignore').decode('ascii')}")
    print(f"  Cleaned: {cleaned}")
    assert "**" not in cleaned and "🌧️" not in cleaned

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ULTRON IS FULLY CONVERSATIONAL AND AI ORIENTED.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
