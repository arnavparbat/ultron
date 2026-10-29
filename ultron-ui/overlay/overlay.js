import { UltronSphere } from "./sphere.js";

const WS_URL = "ws://127.0.0.1:8765";

class UltronOverlayController {
  constructor() {
    this.ws = null;
    this.sphere = null;
    this.isMuted = false;
    this.reconnectTimer = null;

    this.statusDisplay = document.getElementById("status-display");
    this.commandDisplay = document.getElementById("command-display");
    this.responseText = document.getElementById("response-text");
    this.responseBox = document.getElementById("chat-response-box");
    this.onlineDot = document.getElementById("online-dot");
    this.btnWake = document.getElementById("btn-wake");
    this.btnMute = document.getElementById("btn-mute");
    this.btnDash = document.getElementById("btn-dash");
    this.btnMode = document.getElementById("btn-mode");
    this.btnAi = document.getElementById("btn-ai");
    this.aiBadge = document.getElementById("ai-provider-badge");
    this.chatForm = document.getElementById("chat-form");
    this.chatInput = document.getElementById("chat-input");
    this.chipWeather = document.getElementById("chip-weather");

    this.isAlwaysOnTop = false;

    this.initSphere();
    this.initWebSocket();
    this.setupInteractivity();
    this.setupControls();
  }

  initSphere() {
    const container = document.getElementById("sphere-canvas-container");
    this.sphere = new UltronSphere(container);
  }

  setupInteractivity() {
    // Non-blocking click-through management
    const interactiveElements = document.querySelectorAll(".interactive, input, button");
    interactiveElements.forEach((el) => {
      el.addEventListener("mouseenter", () => {
        if (window.electronAPI) {
          window.electronAPI.setIgnoreMouseEvents(false);
        }
      });
      el.addEventListener("mouseleave", () => {
        // If chat input is currently focused, do not ignore mouse events
        if (document.activeElement === this.chatInput) return;
        if (window.electronAPI) {
          window.electronAPI.setIgnoreMouseEvents(true, { forward: true });
        }
      });
    });

    if (this.chatInput) {
      this.chatInput.addEventListener("focus", () => {
        if (window.electronAPI) {
          window.electronAPI.setIgnoreMouseEvents(false);
        }
      });
      this.chatInput.addEventListener("blur", () => {
        if (window.electronAPI) {
          window.electronAPI.setIgnoreMouseEvents(true, { forward: true });
        }
      });
    }
  }

  setupControls() {
    this.btnWake.addEventListener("click", () => {
      this.send({ action: "trigger_wake" });
    });

    this.btnMute.addEventListener("click", () => {
      this.send({ action: "toggle_mute" });
    });

    this.btnDash.addEventListener("click", () => {
      if (window.electronAPI) {
        window.electronAPI.openDashboard();
      }
    });

    if (this.btnAi) {
      this.btnAi.addEventListener("click", () => {
        if (window.electronAPI) {
          window.electronAPI.openDashboard();
        }
      });
    }

    // Chat form submission
    if (this.chatForm) {
      this.chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const cmd = this.chatInput.value.trim();
        if (cmd) {
          this.commandDisplay.textContent = `You: "${cmd}"`;
          this.send({ action: "send_text_command", command: cmd });
          this.chatInput.value = "";
        }
      });
    }

    // Quick action chips
    if (this.chipWeather) {
      this.chipWeather.addEventListener("click", () => {
        this.send({ action: "send_text_command", command: "what is the weather of this place" });
      });
    }

    document.getElementById("chip-chatgpt").addEventListener("click", () => {
      this.send({ action: "send_text_command", command: "open chatgpt.com" });
    });

    document.getElementById("chip-youtube").addEventListener("click", () => {
      this.send({ action: "send_text_command", command: "open youtube.com" });
    });

    const chipScreen = document.getElementById("chip-screen");
    if (chipScreen) {
      chipScreen.addEventListener("click", () => {
        this.send({ action: "send_text_command", command: "show my screen time" });
      });
    }

    const chipSleep = document.getElementById("chip-sleep");
    if (chipSleep) {
      chipSleep.addEventListener("click", () => {
        this.send({ action: "send_text_command", command: "go to sleep" });
      });
    }

    // Window mode toggle button ('DESK' vs 'TOP')
    if (this.btnMode) {
      this.btnMode.addEventListener("click", () => {
        const targetMode = this.isAlwaysOnTop ? "desktop" : "always-on-top";
        if (window.electronAPI && window.electronAPI.setWindowMode) {
          window.electronAPI.setWindowMode(targetMode);
        }
      });
    }

    // Handle Tray triggers via Electron IPC
    if (window.electronAPI) {
      window.electronAPI.onTriggerWake(() => {
        this.send({ action: "trigger_wake" });
      });
      window.electronAPI.onToggleMuteFromTray(() => {
        this.send({ action: "toggle_mute" });
      });
      if (window.electronAPI.onWindowModeChanged) {
        window.electronAPI.onWindowModeChanged((isOnTop) => {
          this.updateModeBadge(isOnTop);
        });
      }
    }
  }

  initWebSocket() {
    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        console.log("[Ultron UI] Connected to Python backend");
        this.onlineDot.style.backgroundColor = "#00ff88";
        this.onlineDot.style.boxShadow = "0 0 8px #00ff88";
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleBackendMessage(data);
        } catch (e) {
          console.error("Error parsing message", e);
        }
      };

      this.ws.onclose = () => {
        console.log("[Ultron UI] Backend disconnected. Retrying in 2s...");
        this.onlineDot.style.backgroundColor = "#ff3355";
        this.onlineDot.style.boxShadow = "0 0 8px #ff3355";
        this.statusDisplay.textContent = "OFFLINE";
        this.statusDisplay.className = "status-value";
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = setTimeout(() => this.initWebSocket(), 2000);
      };

      this.ws.onerror = (err) => {
        this.ws.close();
      };
    } catch (err) {
      console.error("WS error:", err);
    }
  }

  send(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  handleBackendMessage(data) {
    if (data.type === "init") {
      this.updateState(data.state || "idle");
      this.updateMuteState(data.is_muted);
      if (data.ai_status && this.aiBadge) {
        this.aiBadge.textContent = "AI: " + (data.ai_status.provider || "HYBRID").toUpperCase();
      }
    } else if (data.type === "state") {
      this.updateState(data.state, data);
    } else if (data.type === "mute_status") {
      this.updateMuteState(data.is_muted);
    } else if (data.type === "ai_status") {
      if (data.status && this.aiBadge) {
        this.aiBadge.textContent = "AI: " + (data.status.provider || "HYBRID").toUpperCase();
      }
    } else if (data.type === "chat_message") {
      if (data.sender === "user") {
        this.commandDisplay.textContent = `You: "${data.text}"`;
      } else if (data.sender === "ultron") {
        if (this.responseText) {
          this.responseText.textContent = data.text;
          if (this.responseBox) {
            this.responseBox.scrollTop = this.responseBox.scrollHeight;
          }
        }
      }
    } else if (data.type === "event" && data.event === "open_dashboard") {
      if (window.electronAPI) {
        window.electronAPI.openDashboard();
      }
    } else if (data.type === "event" && data.event === "window_mode") {
      const mode = (data.data && data.data.mode) || "desktop";
      if (window.electronAPI && window.electronAPI.setWindowMode) {
        window.electronAPI.setWindowMode(mode);
      }
      this.updateModeBadge(mode === "always-on-top");
    }
  }

  updateModeBadge(isOnTop) {
    this.isAlwaysOnTop = isOnTop;
    if (!this.btnMode) return;
    if (this.isAlwaysOnTop) {
      this.btnMode.textContent = "TOP";
      this.btnMode.classList.add("active");
      this.btnMode.title = "Mode: Always on Top ('Come to me' active) - Click to return to Desktop";
    } else {
      this.btnMode.textContent = "DESK";
      this.btnMode.classList.remove("active");
      this.btnMode.title = "Mode: Desktop Only (Active) - Say 'Come to me' or click to bring on top";
    }
  }

  updateMuteState(muted) {
    this.isMuted = muted;
    if (this.isMuted) {
      this.btnMute.classList.add("active");
      this.btnMute.textContent = "MUTED";
    } else {
      this.btnMute.classList.remove("active");
      this.btnMute.textContent = "MIC";
    }
  }

  updateState(state, meta = {}) {
    if (this.sphere) {
      this.sphere.setState(state);
    }

    this.statusDisplay.textContent = state.toUpperCase();
    this.statusDisplay.className = `status-value ${state}`;

    if (state === "idle") {
      if (!this.commandDisplay.textContent.startsWith("You:")) {
        this.commandDisplay.textContent = "Ready. Awaiting voice or typed input...";
      }
    } else if (state === "listening") {
      this.commandDisplay.textContent = "Listening to your voice...";
    } else if (state === "processing") {
      const cmd = meta.command ? `"${meta.command}"` : "";
      this.commandDisplay.textContent = `Processing: ${cmd}`;
    } else if (state === "complete") {
      const res = meta.result || "Complete, boss.";
      if (this.responseText && !this.responseText.textContent.includes(res)) {
        this.responseText.textContent = res;
      }
    }
  }
}

window.addEventListener("DOMContentLoaded", () => {
  new UltronOverlayController();
});
