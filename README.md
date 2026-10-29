# ULTRON — Desktop AI Voice Assistant

**Ultron** is a full-stack Windows desktop AI assistant combining a background Python automation engine with a futuristic, holographic always-on-top Electron overlay featuring a real-time reactive 3D Three.js wireframe sphere.

---

## Key Capabilities

- **Full AI Brain & Free Conversational Intelligence**:
  - Multi-Engine LLM Support: Groq (Llama 3.3 70B), Google Gemini (2.0 / 1.5 Flash), OpenAI (GPT-4o), Ollama (Local offline models), and OpenRouter.
  - Zero-Key Smart Fallback: Immediate out-of-the-box intelligence without needing any API key!
  - Talkative & Conversational Mode: Ultron talks freely about science, philosophy, history, coding, or any topic with James Spader's iconic Ultron persona.
  - Multi-Turn Dialogue Memory: Retains conversational context for coherent back-and-forth discussions and follow-up questions.
- **Live Weather & Geolocation Radar**:
  - Real-time global and local atmospheric telemetry via wttr.in and Open-Meteo.
  - Automatic IP geolocation: Ask *"What's the weather of this place?"* or *"What's the weather in Tokyo?"* to get real live temperature, weather conditions, humidity, and winds!
- **Interactive Chat Input Bar & Response Bubble**:
  - Always-on-top holographic HUD features a cyberpunk text chat bar and speech response bubble so you can both speak ("Hey Ultron") or type questions freely.
- **Dedicated AI Brain & Intelligence Dashboard Tab**:
  - Switch providers, enter API keys, test connections with live latency metrics, and chat directly in the UI.
- **Wake Word Recognition ("Hey Ultron")**:
  - Offline wake word spotting powered by Picovoice Porcupine (with automatic fallback to continuous speech keyword recognition and UI trigger chips).
  - Low CPU usage background listener.
- **Natural Neural Human-Like Voice (Microsoft Edge Neural TTS)**:
  - Deep, calm, confident male persona (*en-US-ChristopherNeural* / *en-GB-RyanNeural*).
  - Pre-cached high-frequency phrases for instant (<50ms) "Yes boss", "Done, boss", and power confirmations.
- **System Power & Workstation Automation (Sleep, Shutdown, Restart)**:
  - Native Windows OS power execution coordinated smoothly with voice speech.
  - Ultron speaks a confirmation in his iconic metallic voice before initiating power actions.
  - Supported voice wake phrases and text commands:
    - *"ultron go to sleep"* / *"hey ultron go to sleep"* / *"sleep"* / *"put my pc to sleep"* / *"enter sleep mode"*
    - *"ultron shutdown"* / *"hey ultron shutdown"* / *"shut down"* / *"turn off my pc"* / *"power off"*
    - *"ultron restart"* / *"hey ultron restart"* / *"reboot"* / *"restart my computer"*
    - *"cancel shutdown"* / *"abort shutdown"*
  - Quick-action "🌙 Sleep" chip directly on the holographic HUD overlay.
- **File Explorer & Media Automation (Videos in VLC Only & Documents in Default Handlers)**:
  - Deep File Search across D: drive first, user standard directories (Downloads, Videos, Documents, Desktop, OneDrive), and C: drive with smart system folder exclusion and <1ms caching.
  - **Videos strictly open in VLC Media Player**: Any video (.mp4, .mkv, .avi, .mov, .wmv, .flv, .webm, etc.) is automatically launched in `vlc.exe`.
  - **Documents open in System Default Programs**: PDF (.pdf), PowerPoint (.ppt, .pptx), Word Documents (.doc, .docx), Spreadsheets (.xls, .xlsx, .csv), and text files open in their respective default Windows applications.
  - Natural voice and typed commands supported:
    - *"open bigg boss video"* / *"play bigg boss"* / *"open in vlc breaking bad"*
    - *"open pitch deck ppt"* / *"open presentation pitch deck"*
    - *"open coep hostel fee pdf"*
    - *"open performance analysis doc"*
    - *"open data4 excel"* / *"open file data4"*
    - *"open report.pdf"* / *"access video sample"*
- **Folder Navigation & Drive Explorer**:
  - Voice navigation for File Explorer: *"open file explorer"*, *"open d drive"*, *"open c drive"*, *"open [name] folder"*.
- **App Launching with Fuzzy Pronunciation Matching**:
  - Auto-scans Start Menu, Desktop shortcuts, and Windows programs on first run.
  - Resolves colloquial and misspelled names using `rapidfuzz` (e.g. "open valorant", "launch code", "start spotify").
- **Website Opening & Domain Auto-Typing**:
  - Recognizes domains (e.g. `.com`, `.ai`, `.org`, `.in`, `.net`) and phonetic speech ("chatgpt dot com", "youtube dot com", "open reddit").
  - Focuses browser address bar via `pyautogui` keyboard automation and navigates reliably.
- **Continuous Screen Time & Network Usage Tracker**:
  - Background daemon logging active foreground window and process name into SQLite (`ultron_usage.db`).
  - Correlates network I/O delta to active applications.
  - Aggregates daily screen time, monthly trend curves, and per-app breakdowns.
- **Hacker Cyberpunk Holographic Overlay & 3D Wireframe Sphere**:
  - Frameless, transparent, always-on-top window with smart non-blocking click-through (`setIgnoreMouseEvents`).
  - Multi-ring icosahedron wireframe sphere in Three.js with glowing vertex nodes and an animated pulsing core.
  - 4 Dynamic States:
    - **Idle**: Cool cyan/green wireframe (`#00f0ff`), slow clockwise rotation.
    - **Listening**: Scales up smoothly (+32%), shifts to intense gold/amber (`#ffaa00`), rotation slows attentively.
    - **Processing**: Vibrates and jitters with rapid line/positional shake while speaking "Yes boss" and executing.
    - **Complete**: Vibration halts, sphere smoothly transitions back to cyan/green and returns to idle.
- **Telemetry Dashboard**:
  - Interactive window with Chart.js charts for daily screen time, monthly trends, network data usage, voice command logs, and searchable app aliases.
- **Windows Boot Auto-Start**:
  - Automatically registers `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` to launch silently into the system tray on Windows startup.

---

## Directory Structure

```
C:\Users\ASUS\Ultron\
├── data\
│   ├── ultron_usage.db          # SQLite database (screen time, commands, network)
│   ├── aliases.json             # Scanned application aliases map
│   └── audio_cache\             # Pre-cached instant neural speech files
├── ultron-backend\
│   ├── server.py                # WebSocket server & orchestrator (ws://127.0.0.1:8765)
│   ├── wake_detector.py         # Porcupine & Continuous speech recognizer
│   ├── voice_service.py         # Neural TTS & instant audio player
│   ├── app_launcher.py          # Start Menu scanner & rapidfuzz matcher
│   ├── website_opener.py        # Spoken domain parser & browser automation
│   ├── system_commands.py       # Volume, media, screenshots, lock screen
│   ├── usage_tracker.py         # Background foreground window & network tracker
│   ├── database.py              # SQLite storage & aggregation queries
│   ├── autostart.py             # Windows Registry startup manager
│   └── config.py                # Centralized configuration
├── ultron-ui\
│   ├── main.js                  # Electron main process (overlay, tray, dashboard, IPC)
│   ├── preload.js               # Context bridge for mouse events and IPC
│   ├── overlay\
│   │   ├── index.html           # Holographic overlay HUD
│   │   ├── overlay.css          # CRT scanlines, neon badges, hacker theme
│   │   ├── sphere.js            # Three.js 3D wireframe sphere animation
│   │   └── overlay.js           # WebSocket client & HUD state manager
│   ├── dashboard\
│   │   ├── index.html           # Telemetry dashboard
│   │   ├── dashboard.css        # Cyberpunk dashboard styling
│   │   └── dashboard.js         # Chart.js visualizations & alias manager
│   └── vendor\                  # Local Three.js and Chart.js bundles
├── start.bat                    # One-click Windows batch launcher
├── start.ps1                    # PowerShell launcher (supports -Silent flag)
└── requirements.txt             # Python dependencies
```

---

## How to Run

### Quick Launch
Double-click `start.bat` or run in PowerShell:
```powershell
cd C:\Users\ASUS\Ultron
.\start.bat
```

To run in the background silently (as on boot):
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Silent
```

To stop Ultron:
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Stop
```

---

## Voice Commands Guide

| Voice Command | Action |
| --- | --- |
| *"Hey Ultron, what is the weather of this place?"* | Auto-detects location via IP and speaks live weather, temperature, humidity, and winds |
| *"Hey Ultron, what's the weather in Tokyo / London?"* | Fetches and speaks live weather for any city worldwide |
| *"Hey Ultron, why is the sky blue?"* | Ultron explains the scientific concept articulately |
| *"Hey Ultron, who was Nikola Tesla / Albert Einstein?"* | Speaks detailed biographical and historical knowledge |
| *"Hey Ultron, what is 125 times 8?"* | Computes math calculations and formulas |
| *"Hey Ultron, tell me a joke"* | Shares witty humor in Ultron persona |
| *"Hey Ultron, clear conversation memory"* | Wipes conversational memory for a fresh topic |
| *"Hey Ultron, come to me"* | Brings holographic overlay on top of all active application windows |
| *"Hey Ultron, go to desktop"* | Returns overlay to desktop level (stays behind active apps) |
| *"Hey Ultron, open Chrome / Notepad / Spotify"* | Launches application via alias map or fuzzy matcher |
| *"Hey Ultron, open chatgpt.com"* | Normalizes URL, focuses browser, types URL |
| *"Hey Ultron, open youtube dot com"* | Opens YouTube in browser |
| *"Hey Ultron, show my screen time"* | Speaks today's screen time and opens Dashboard |
| *"Hey Ultron, take a screenshot"* | Captures screen to `Pictures\Ultron_Screenshots` |
| *"Hey Ultron, volume up / down / mute"* | Controls system audio volume |
| *"Hey Ultron, lock my pc"* | Locks Windows workstation |
| *"Hey Ultron, what time is it?"* | Speaks current time |
| *"Hey Ultron, system status"* | Reports CPU, RAM, and battery telemetry |
| *"Hey Ultron, rescan apps"* | Refreshes Start Menu shortcuts and aliases |

---

## Configuration & Customization

Edit `ultron-backend\config.py`:
- `PORCUPINE_ACCESS_KEY`: Picovoice access key for custom offline wake words.
- `TTS_VOICE`: Choose between neural voices (e.g. `en-US-ChristopherNeural`, `en-GB-RyanNeural`, `en-US-GuyNeural`).
- `STT_PAUSE_THRESHOLD`: Silence duration to conclude speech (default 0.8s).
