const WS_URL = "ws://127.0.0.1:8765";

class UltronDashboard {
  constructor() {
    this.ws = null;
    this.charts = {};
    this.aliases = {};
    this.customAliases = new Set();
    this.showCustomOnly = false;
    this.dashboardData = null;
    this.autostart = false;

    this.initWebSocket();
    this.setupTabs();
    this.setupButtons();
    this.setupCustomAppHandlers();
    this.setupAIBrainHandlers();
  }

  setupTabs() {
    const tabs = document.querySelectorAll(".tab-item");
    const contents = document.querySelectorAll(".tab-content");

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("active"));
        contents.forEach((c) => (c.style.display = "none"));

        tab.classList.add("active");
        const targetId = tab.getAttribute("data-tab");
        const targetContent = document.getElementById(targetId);
        if (targetContent) {
          targetContent.style.display = "block";
        }
        if (targetId === "tab-aliases") {
          const searchVal = document.getElementById("alias-search") ? document.getElementById("alias-search").value : "";
          this.renderAliasesTable(searchVal);
        }
      });
    });

    const appsCard = document.getElementById("card-apps-summary");
    if (appsCard) {
      appsCard.addEventListener("click", () => {
        const aliasTab = document.querySelector('[data-tab="tab-aliases"]');
        if (aliasTab) aliasTab.click();
      });
    }
  }

  setupButtons() {
    document.getElementById("btn-refresh").addEventListener("click", () => {
      this.fetchData();
    });

    document.getElementById("btn-toggle-autostart").addEventListener("click", () => {
      this.send({ action: "toggle_autostart" });
    });

    document.getElementById("btn-rescan-apps").addEventListener("click", () => {
      this.send({ action: "rescan_apps" });
    });

    const btnFilterCustom = document.getElementById("btn-filter-custom");
    if (btnFilterCustom) {
      btnFilterCustom.addEventListener("click", () => {
        this.showCustomOnly = !this.showCustomOnly;
        btnFilterCustom.classList.toggle("active-filter", this.showCustomOnly);
        btnFilterCustom.textContent = this.showCustomOnly ? "SHOW ALL" : "SHOW CUSTOM ONLY";
        const searchVal = document.getElementById("alias-search") ? document.getElementById("alias-search").value : "";
        this.renderAliasesTable(searchVal);
      });
    }

    const searchInput = document.getElementById("alias-search");
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        this.renderAliasesTable(e.target.value);
      });
    }
  }

  initWebSocket() {
    this.ws = new WebSocket(WS_URL);

    this.ws.onopen = () => {
      console.log("[Dashboard] Connected to backend");
      document.getElementById("system-status-badge").textContent = "ONLINE";
      document.getElementById("system-status-badge").style.borderColor = "#00ff88";
      this.fetchData();
      this.send({ action: "get_app_aliases" });
      this.send({ action: "get_ai_status" });
      this.send({ action: "get_weather" });
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      } catch (e) {
        console.error("Dashboard error parsing message:", e);
      }
    };

    this.ws.onclose = () => {
      document.getElementById("system-status-badge").textContent = "OFFLINE";
      document.getElementById("system-status-badge").style.borderColor = "#ff3355";
      setTimeout(() => this.initWebSocket(), 2500);
    };
  }

  send(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  fetchData() {
    this.send({ action: "get_dashboard_data" });
  }

  handleMessage(data) {
    if (data.type === "init") {
      this.autostart = data.autostart;
      this.updateAutostartButton();
      if (data.custom_aliases) {
        this.customAliases = new Set(data.custom_aliases);
      }
      if (data.ai_status) {
        this.updateAIStatus(data.ai_status, data.location);
      }
    } else if (data.type === "ai_status") {
      this.updateAIStatus(data.status, data.location);
    } else if (data.type === "ai_config_saved") {
      this.showAIFeedback("AI configuration saved successfully!", "success");
      if (data.status) this.updateAIStatus(data.status);
    } else if (data.type === "ai_test_result") {
      this.showAIFeedback(data.message, data.success ? "success" : "error");
    } else if (data.type === "weather_data") {
      this.updateWeatherDisplay(data.data, data.location);
    } else if (data.type === "chat_message") {
      this.appendDashboardChatMessage(data.sender, data.text);
    } else if (data.type === "chat_history_cleared") {
      this.showAIFeedback("Conversational memory cleared.", "success");
      const box = document.getElementById("ai-chat-history-box");
      if (box) {
        box.innerHTML = `<div style="color: #00ff88; font-size: 12px; line-height: 1.4;">
          <strong>ULTRON:</strong> Memory wiped, boss. Ready for a clean slate.
        </div>`;
      }
    } else if (data.type === "autostart_status") {
      this.autostart = data.autostart;
      this.updateAutostartButton();
    } else if (data.type === "dashboard_data") {
      this.dashboardData = data.data;
      this.renderDashboard(data.data);
    } else if (data.type === "app_aliases") {
      this.aliases = data.aliases || {};
      this.customAliases = new Set(data.custom_aliases || []);
      document.getElementById("val-apps-count").textContent = Object.keys(this.aliases).length;
      const countBadge = document.getElementById("aliases-count-badge");
      if (countBadge) countBadge.textContent = `${Object.keys(this.aliases).length} TOTAL`;
      const searchVal = document.getElementById("alias-search") ? document.getElementById("alias-search").value : "";
      this.renderAliasesTable(searchVal);
    } else if (data.type === "alias_added") {
      if (data.success) {
        this.showAddFeedback(`✓ Registered "${data.name}"! Say "Hey Ultron, open ${data.name}" or "open ${data.name} for me".`, "success");
        const nameInput = document.getElementById("input-app-name");
        const pathInput = document.getElementById("input-app-path");
        if (nameInput) nameInput.value = "";
        if (pathInput) pathInput.value = "";
        this.aliases = data.aliases || this.aliases;
        this.customAliases = new Set(data.custom_aliases || []);
        document.getElementById("val-apps-count").textContent = Object.keys(this.aliases).length;
        const countBadge = document.getElementById("aliases-count-badge");
        if (countBadge) countBadge.textContent = `${Object.keys(this.aliases).length} TOTAL`;
        const searchVal = document.getElementById("alias-search") ? document.getElementById("alias-search").value : "";
        this.renderAliasesTable(searchVal);
      } else {
        this.showAddFeedback("Registration failed: " + (data.message || "Unknown error"), "error");
      }
    } else if (data.type === "alias_removed") {
      if (data.success) {
        this.showAddFeedback(`✓ Removed application alias "${data.name}".`, "info");
        this.aliases = data.aliases || this.aliases;
        this.customAliases = new Set(data.custom_aliases || []);
        document.getElementById("val-apps-count").textContent = Object.keys(this.aliases).length;
        const countBadge = document.getElementById("aliases-count-badge");
        if (countBadge) countBadge.textContent = `${Object.keys(this.aliases).length} TOTAL`;
        const searchVal = document.getElementById("alias-search") ? document.getElementById("alias-search").value : "";
        this.renderAliasesTable(searchVal);
      }
    }
  }

  updateAutostartButton() {
    const btn = document.getElementById("btn-toggle-autostart");
    if (this.autostart) {
      btn.textContent = "BOOT AUTO-START: ON";
      btn.style.color = "#00ff88";
      btn.style.borderColor = "#00ff88";
    } else {
      btn.textContent = "BOOT AUTO-START: OFF";
      btn.style.color = "#ffaa00";
      btn.style.borderColor = "#ffaa00";
    }
  }

  formatBytes(bytes) {
    if (!bytes || bytes <= 0) return "0.0 MB";
    const mb = bytes / (1024 * 1024);
    if (mb >= 1024) {
      return (mb / 1024).toFixed(2) + " GB";
    }
    return mb.toFixed(1) + " MB";
  }

  renderDashboard(data) {
    const daily = data.daily_screen_time || {};
    const monthly = data.monthly_screen_time || {};
    const network = data.data_usage || {};
    const commands = data.recent_commands || [];

    // 1. Metric Cards
    document.getElementById("val-daily-time").textContent = `${daily.total_hours || 0.0}h`;
    document.getElementById("sub-daily-time").textContent = `${daily.total_minutes || 0} mins tracked today`;

    document.getElementById("val-monthly-time").textContent = `${monthly.total_hours || 0.0}h`;
    document.getElementById("sub-monthly-time").textContent = `${monthly.month || ""} total screen time`;

    const todayBytes = (network.daily && network.daily.total_bytes) || 0;
    document.getElementById("val-daily-data").textContent = this.formatBytes(todayBytes);

    // 2. Daily Apps Chart
    this.renderDailyAppsChart(daily.apps || []);

    // 3. Monthly Trend Chart
    this.renderMonthlyTrendChart(monthly.daily_trend || []);

    // 4. Daily Apps Table
    this.renderDailyAppsTable(daily.apps || [], daily.total_seconds || 1);

    // 5. Data Usage Charts
    this.renderDataUsageCharts(network);

    // 6. Command History Table
    this.renderCommandsTable(commands);
  }

  renderDailyAppsChart(apps) {
    const topApps = apps.slice(0, 7);
    const labels = topApps.map((a) => a.process_name);
    const data = topApps.map((a) => a.minutes);

    const ctx = document.getElementById("chart-daily-apps").getContext("2d");
    if (this.charts.dailyApps) this.charts.dailyApps.destroy();

    this.charts.dailyApps = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels.length ? labels : ["No Activity Yet"],
        datasets: [{
          label: "Minutes Active",
          data: data.length ? data : [0],
          backgroundColor: "rgba(0, 240, 255, 0.45)",
          borderColor: "#00f0ff",
          borderWidth: 1.5,
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#88aacc", font: { family: "Share Tech Mono" } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#88aacc", font: { family: "Share Tech Mono" } }
          }
        }
      }
    });
  }

  renderMonthlyTrendChart(trends) {
    const labels = trends.map((t) => t.date.slice(5)); // MM-DD
    const data = trends.map((t) => t.hours);

    const ctx = document.getElementById("chart-monthly-trend").getContext("2d");
    if (this.charts.monthlyTrend) this.charts.monthlyTrend.destroy();

    this.charts.monthlyTrend = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels.length ? labels : ["Today"],
        datasets: [{
          label: "Hours per Day",
          data: data.length ? data : [0],
          borderColor: "#00ff88",
          backgroundColor: "rgba(0, 255, 136, 0.15)",
          borderWidth: 2,
          tension: 0.3,
          fill: true,
          pointBackgroundColor: "#00ff88"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#88aacc", font: { family: "Share Tech Mono" } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#88aacc", font: { family: "Share Tech Mono" } }
          }
        }
      }
    });
  }

  renderDataUsageCharts(network) {
    const dailyApps = (network.daily && network.daily.apps) ? network.daily.apps.slice(0, 6) : [];
    const monthlyApps = (network.monthly && network.monthly.apps) ? network.monthly.apps.slice(0, 6) : [];

    const ctxDaily = document.getElementById("chart-data-daily").getContext("2d");
    if (this.charts.dataDaily) this.charts.dataDaily.destroy();

    this.charts.dataDaily = new Chart(ctxDaily, {
      type: "doughnut",
      data: {
        labels: dailyApps.map(a => a.process_name),
        datasets: [{
          data: dailyApps.map(a => Math.round(a.total_bytes / (1024 * 1024))),
          backgroundColor: ["#00f0ff", "#00ff88", "#ffaa00", "#b366ff", "#ff3366", "#3399ff"]
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "right", labels: { color: "#88aacc", font: { family: "Share Tech Mono" } } }
        }
      }
    });

    const ctxMonthly = document.getElementById("chart-data-monthly").getContext("2d");
    if (this.charts.dataMonthly) this.charts.dataMonthly.destroy();

    this.charts.dataMonthly = new Chart(ctxMonthly, {
      type: "bar",
      data: {
        labels: monthlyApps.map(a => a.process_name),
        datasets: [{
          label: "MB Transferred",
          data: monthlyApps.map(a => Math.round(a.total_bytes / (1024 * 1024))),
          backgroundColor: "rgba(255, 170, 0, 0.4)",
          borderColor: "#ffaa00",
          borderWidth: 1.5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#88aacc", font: { family: "Share Tech Mono" } } },
          y: { ticks: { color: "#88aacc", font: { family: "Share Tech Mono" } } }
        }
      }
    });
  }

  renderDailyAppsTable(apps, totalSeconds) {
    const tbody = document.getElementById("table-daily-apps");
    if (!apps || apps.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#5588aa;">No app sessions recorded yet today.</td></tr>';
      return;
    }

    tbody.innerHTML = apps.map((app) => {
      const share = totalSeconds > 0 ? ((app.seconds / totalSeconds) * 100).toFixed(1) : "0.0";
      return `
        <tr>
          <td style="font-weight: bold; color: #fff;">${app.process_name}</td>
          <td>${app.hours > 0 ? `${app.hours}h (${app.minutes}m)` : `${app.minutes} mins`}</td>
          <td>${this.formatBytes(app.bytes)}</td>
          <td>
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="flex:1; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden;">
                <div style="width: ${share}%; height: 100%; background: #00f0ff;"></div>
              </div>
              <span style="font-size: 11px;">${share}%</span>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }

  renderCommandsTable(commands) {
    const tbody = document.getElementById("table-commands");
    if (!commands || commands.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#5588aa;">No voice commands logged yet. Say "Hey Ultron" to execute tasks!</td></tr>';
      return;
    }

    tbody.innerHTML = commands.map((c) => {
      const isOk = c.execution_status === "success";
      const statusClass = isOk ? "success" : "failed";
      return `
        <tr>
          <td style="color: #6482a0; font-size: 11px;">${c.timestamp || ""}</td>
          <td style="color: #ffffff; font-weight: bold;">"${c.raw_text}"</td>
          <td style="color: #00f0ff;">${c.command_type}</td>
          <td><span class="status-tag ${statusClass}">${(c.execution_status || "").toUpperCase()}</span></td>
          <td style="color: #d0e8ff; font-size: 11px;">${c.execution_result || ""}</td>
        </tr>
      `;
    }).join("");
  }

  setupCustomAppHandlers() {
    // 1. Browse PC button
    const btnBrowse = document.getElementById("btn-browse-app");
    if (btnBrowse) {
      btnBrowse.addEventListener("click", async () => {
        try {
          if (window.electronAPI && typeof window.electronAPI.browseAppFile === "function") {
            const filePath = await window.electronAPI.browseAppFile();
            if (filePath) {
              document.getElementById("input-app-path").value = filePath;
              const nameInput = document.getElementById("input-app-name");
              if (!nameInput.value.trim()) {
                nameInput.value = this.extractAppName(filePath);
              }
              nameInput.focus();
            }
          } else {
            // Web browser fallback
            const input = document.createElement("input");
            input.type = "file";
            input.accept = ".exe,.lnk,.bat,.cmd,.url,*";
            input.onchange = (e) => {
              const file = e.target.files[0];
              if (file) {
                const path = file.path || file.name;
                document.getElementById("input-app-path").value = path;
                const nameInput = document.getElementById("input-app-name");
                if (!nameInput.value.trim()) {
                  nameInput.value = this.extractAppName(file.name);
                }
              }
            };
            input.click();
          }
        } catch (err) {
          console.error("Browse app error:", err);
          this.showAddFeedback("Browse error: " + err.message, "error");
        }
      });
    }

    // 2. Add App Form submit
    const formAdd = document.getElementById("form-add-app");
    if (formAdd) {
      formAdd.addEventListener("submit", (e) => {
        e.preventDefault();
        this.submitCustomApp();
      });
    }

    const btnAdd = document.getElementById("btn-add-app");
    if (btnAdd) {
      btnAdd.addEventListener("click", (e) => {
        e.preventDefault();
        this.submitCustomApp();
      });
    }
  }

  extractAppName(filePath) {
    if (!filePath) return "";
    const clean = filePath.replace(/\\/g, "/");
    const parts = clean.split("/");
    let name = parts[parts.length - 1] || "";
    name = name.replace(/\.[^/.]+$/, ""); // strip extension
    name = name.replace(/\s*-\s*shortcut/i, "").replace(/\s*shortcut/i, "");
    return name.trim().toLowerCase();
  }

  submitCustomApp() {
    const nameInput = document.getElementById("input-app-name");
    const pathInput = document.getElementById("input-app-path");
    const name = (nameInput ? nameInput.value : "").trim();
    const appPath = (pathInput ? pathInput.value : "").trim();

    if (!name) {
      this.showAddFeedback("Please enter a spoken application name/alias.", "error");
      if (nameInput) nameInput.focus();
      return;
    }
    if (!appPath) {
      this.showAddFeedback("Please browse or enter the executable path.", "error");
      if (pathInput) pathInput.focus();
      return;
    }

    this.send({
      action: "add_app_alias",
      name: name,
      path: appPath
    });

    this.showAddFeedback(`Registering "${name}" with Ultron...`, "info");
  }

  deleteCustomApp(name) {
    if (confirm(`Are you sure you want to remove application alias "${name}"?`)) {
      this.send({
        action: "remove_app_alias",
        name: name
      });
    }
  }

  showAddFeedback(msg, type = "success") {
    const el = document.getElementById("add-app-feedback");
    if (!el) return;
    el.textContent = msg;
    el.style.display = "block";
    if (type === "success") {
      el.style.background = "rgba(0, 255, 136, 0.15)";
      el.style.border = "1px solid #00ff88";
      el.style.color = "#00ff88";
    } else if (type === "info") {
      el.style.background = "rgba(0, 240, 255, 0.15)";
      el.style.border = "1px solid #00f0ff";
      el.style.color = "#00f0ff";
    } else {
      el.style.background = "rgba(255, 51, 85, 0.15)";
      el.style.border = "1px solid #ff3355";
      el.style.color = "#ff3355";
    }

    if (type === "success") {
      setTimeout(() => {
        if (el.textContent === msg) {
          el.style.display = "none";
        }
      }, 5000);
    }
  }

  renderAliasesTable(filter = "") {
    const tbody = document.getElementById("table-aliases");
    if (!tbody) return;
    const query = filter.toLowerCase().trim();
    let keys = Object.keys(this.aliases);

    // Filter by search query
    if (query) {
      keys = keys.filter(k => k.includes(query) || (this.aliases[k] && this.aliases[k].toLowerCase().includes(query)));
    }

    // Filter by custom-only if toggled
    if (this.showCustomOnly) {
      keys = keys.filter(k => this.customAliases.has(k));
    }

    // Sort: custom aliases first, then alphabetical
    keys.sort((a, b) => {
      const aCustom = this.customAliases.has(a);
      const bCustom = this.customAliases.has(b);
      if (aCustom && !bCustom) return -1;
      if (!aCustom && bCustom) return 1;
      return a.localeCompare(b);
    });

    if (keys.length === 0) {
      const msg = this.showCustomOnly 
        ? 'No custom applications registered yet. Use the "REGISTER NEW APPLICATION" form above!' 
        : 'No matching application aliases found.';
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:#5588aa; padding: 20px;">${msg}</td></tr>`;
      return;
    }

    tbody.innerHTML = keys.slice(0, 60).map((name) => {
      const targetPath = this.aliases[name];
      const isCustom = this.customAliases.has(name);
      const sourceBadge = isCustom 
        ? '<span class="badge-custom">CUSTOM</span>' 
        : '<span class="badge-system">SYSTEM</span>';
      
      const escapedName = name.replace(/'/g, "\\'");
      const deleteBtn = isCustom 
        ? `<button class="btn-cyber danger" style="padding: 2px 8px; font-size: 10px; margin-left: 6px;" onclick="window.ultronDash.deleteCustomApp('${escapedName}')">REMOVE</button>` 
        : '';

      return `
        <tr>
          <td style="color: #00ff88; font-weight: bold; font-size: 13px;">${name}</td>
          <td>${sourceBadge}</td>
          <td style="color: #88aacc; font-size: 11px; max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${targetPath}">
            ${targetPath}
          </td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn-cyber" style="padding: 2px 8px; font-size: 10px;" onclick="window.ultronDash.testLaunch('${escapedName}')">LAUNCH</button>
            ${deleteBtn}
          </td>
        </tr>
      `;
    }).join("");
  }

  testLaunch(appName) {
    this.send({ action: "send_text_command", command: `open ${appName}` });
  }

  setupAIBrainHandlers() {
    const providerSelect = document.getElementById("select-ai-provider");
    const modelInput = document.getElementById("input-ai-model");
    const keyInput = document.getElementById("input-ai-key");
    const btnToggleKey = document.getElementById("btn-toggle-key-visibility");
    const formAi = document.getElementById("form-ai-config");
    const btnTest = document.getElementById("btn-test-ai-conn");
    const btnClear = document.getElementById("btn-clear-ai-memory");
    const btnRefreshWeather = document.getElementById("btn-refresh-weather");
    const formWeather = document.getElementById("form-check-weather");
    const formDashChat = document.getElementById("form-dashboard-chat");

    // Provider change auto-fills standard recommended models
    if (providerSelect && modelInput) {
      providerSelect.addEventListener("change", (e) => {
        const val = e.target.value;
        const defaults = {
          groq: "openai/gpt-oss-120b",
          gemini: "gemini-3.6-flash",
          openai: "gpt-4o-mini",
          ollama: "llama3:latest",
          openrouter: "google/gemini-2.0-flash-exp:free",
          hybrid: "built-in"
        };
        modelInput.value = defaults[val] || "";
      });
    }

    // Toggle API Key visibility
    if (btnToggleKey && keyInput) {
      btnToggleKey.addEventListener("click", () => {
        if (keyInput.type === "password") {
          keyInput.type = "text";
          btnToggleKey.textContent = "🙈 HIDE";
        } else {
          keyInput.type = "password";
          btnToggleKey.textContent = "👁 SHOW";
        }
      });
    }

    // Remove / clear API Key button
    const btnRemoveKey = document.getElementById("btn-remove-api-key");
    if (btnRemoveKey) {
      btnRemoveKey.addEventListener("click", () => {
        if (confirm("Remove saved API key? Ultron will fall back to Zero-Key Hybrid mode.")) {
          if (keyInput) keyInput.value = "";
          this.showAIFeedback("Removing saved API key...", "info");
          this.send({
            action: "save_ai_config",
            config: { clear_key: true }
          });
        }
      });
    }

    // Save AI Settings
    if (formAi) {
      formAi.addEventListener("submit", (e) => {
        e.preventDefault();
        const provider = providerSelect ? providerSelect.value : "hybrid";
        const model = modelInput ? modelInput.value.trim() : "";
        const apiKey = keyInput ? keyInput.value.trim() : "";
        const talkative = document.getElementById("select-talkative-mode") ? document.getElementById("select-talkative-mode").value === "true" : true;
        const persona = document.getElementById("select-persona") ? document.getElementById("select-persona").value : "ultron";

        const configPayload = {
          provider: provider,
          model: model,
          talkative_mode: talkative,
          persona: persona
        };

        // Only send api_key if user typed something new.
        // If blank, keep the securely saved key on the server.
        if (apiKey) {
          configPayload.api_key = apiKey;
        }

        this.showAIFeedback("Saving AI configuration...", "info");
        this.send({
          action: "save_ai_config",
          config: configPayload
        });

        // Clear password input so it shows the masked placeholder
        if (keyInput && apiKey) {
          keyInput.value = "";
        }
      });
    }

    // Test connection
    if (btnTest) {
      btnTest.addEventListener("click", () => {
        const provider = providerSelect ? providerSelect.value : "hybrid";
        const model = modelInput ? modelInput.value.trim() : "";
        const apiKey = keyInput ? keyInput.value.trim() : "";
        const hasStoredKey = this.currentAIStatus && this.currentAIStatus.has_key;

        if (provider !== "hybrid" && provider !== "ollama" && !apiKey && !hasStoredKey) {
          this.showAIFeedback(`An API key is required to test the ${provider.toUpperCase()} provider.`, "error");
          return;
        }

        this.showAIFeedback("Connecting to neural endpoint...", "info");
        this.send({
          action: "test_ai_connection",
          provider: provider,
          api_key: apiKey,
          model: model
        });
      });
    }

    // Clear memory
    if (btnClear) {
      btnClear.addEventListener("click", () => {
        this.send({ action: "clear_chat_history" });
      });
    }

    // Weather refresh
    if (btnRefreshWeather) {
      btnRefreshWeather.addEventListener("click", () => {
        const display = document.getElementById("weather-report-display");
        if (display) display.textContent = "Refreshing live atmospheric radar...";
        this.send({ action: "get_weather", location: "" });
      });
    }

    // Weather search query
    if (formWeather) {
      formWeather.addEventListener("submit", (e) => {
        e.preventDefault();
        const cityInput = document.getElementById("input-weather-city");
        const query = cityInput ? cityInput.value.trim() : "";
        if (query) {
          const display = document.getElementById("weather-report-display");
          if (display) display.textContent = `Querying atmospheric conditions for ${query}...`;
          this.send({ action: "get_weather", location: query });
        }
      });
    }

    // Dashboard direct chat transmission
    if (formDashChat) {
      formDashChat.addEventListener("submit", (e) => {
        e.preventDefault();
        const chatInput = document.getElementById("input-dashboard-chat");
        const msg = chatInput ? chatInput.value.trim() : "";
        if (msg) {
          this.send({ action: "send_text_command", command: msg });
          chatInput.value = "";
        }
      });
    }
  }

  updateAIStatus(status, location) {
    if (!status) return;
    this.currentAIStatus = status;
    const providerSelect = document.getElementById("select-ai-provider");
    const modelInput = document.getElementById("input-ai-model");
    const talkativeSelect = document.getElementById("select-talkative-mode");
    const personaSelect = document.getElementById("select-persona");
    const badge = document.getElementById("ai-active-provider-badge");
    const keyInput = document.getElementById("input-ai-key");
    const keyBadge = document.getElementById("ai-key-status-badge");
    const keyHelpText = document.getElementById("ai-key-help-text");
    const btnRemoveKey = document.getElementById("btn-remove-api-key");

    if (providerSelect && status.provider) providerSelect.value = status.provider;
    if (modelInput && status.model) modelInput.value = status.model;
    if (talkativeSelect && status.talkative_mode !== undefined) {
      talkativeSelect.value = String(status.talkative_mode);
    }
    if (personaSelect && status.persona) personaSelect.value = status.persona;

    if (badge) {
      const pName = (status.provider || "HYBRID").toUpperCase();
      const hasKey = status.has_key ? "✓ ACTIVE" : "ZERO-KEY";
      badge.textContent = `${pName} [${hasKey}]`;
      badge.style.color = status.has_key ? "#00ff88" : "#00f0ff";
    }

    // Update Persistent Key Status Display
    if (status.has_key) {
      const mask = status.masked_key || "********";
      if (keyBadge) {
        keyBadge.textContent = "✓ PERMANENTLY SAVED";
        keyBadge.style.background = "rgba(0, 255, 136, 0.15)";
        keyBadge.style.color = "#00ff88";
        keyBadge.style.border = "1px solid rgba(0, 255, 136, 0.3)";
      }
      if (keyInput) {
        keyInput.placeholder = `Saved: ${mask} (Leave blank to keep active key)`;
      }
      if (keyHelpText) {
        keyHelpText.innerHTML = `<span style="color: #00ff88;">🔒 Key permanently saved (<code>${mask}</code>). Stored in <code>.env</code> & <code>data/ai_config.json</code> across restarts.</span>`;
      }
      if (btnRemoveKey) {
        btnRemoveKey.style.display = "inline-block";
      }
    } else {
      if (keyBadge) {
        keyBadge.textContent = "NO KEY SAVED";
        keyBadge.style.background = "rgba(0, 240, 255, 0.08)";
        keyBadge.style.color = "#88aacc";
        keyBadge.style.border = "1px solid rgba(0, 240, 255, 0.15)";
      }
      if (keyInput) {
        keyInput.placeholder = "Enter API key (e.g. AIza... or gsk_...)";
      }
      if (keyHelpText) {
        keyHelpText.innerHTML = `<span style="color: #88aacc;">No API key stored. Enter a key above or save in your <code>.env</code> file.</span>`;
      }
      if (btnRemoveKey) {
        btnRemoveKey.style.display = "none";
      }
    }

    if (location) {
      const locLabel = document.getElementById("weather-location-name");
      if (locLabel) {
        const city = location.city || "Local";
        const country = location.country || "";
        locLabel.textContent = country ? `${city}, ${country}` : city;
      }
    }
  }

  updateWeatherDisplay(weatherText, location) {
    const display = document.getElementById("weather-report-display");
    if (display && weatherText) {
      display.textContent = weatherText;
    }
    if (location) {
      const locLabel = document.getElementById("weather-location-name");
      if (locLabel) {
        const city = location.city || "Local";
        const country = location.country || "";
        locLabel.textContent = country ? `${city}, ${country}` : city;
      }
    }
  }

  showAIFeedback(msg, type = "info") {
    const box = document.getElementById("ai-config-feedback");
    if (!box) return;
    box.style.display = "block";
    box.textContent = msg;

    if (type === "success") {
      box.style.background = "rgba(0, 255, 136, 0.15)";
      box.style.border = "1px solid #00ff88";
      box.style.color = "#00ff88";
    } else if (type === "error") {
      box.style.background = "rgba(255, 50, 70, 0.15)";
      box.style.border = "1px solid #ff3355";
      box.style.color = "#ff5577";
    } else {
      box.style.background = "rgba(0, 240, 255, 0.15)";
      box.style.border = "1px solid #00f0ff";
      box.style.color = "#00f0ff";
    }

    setTimeout(() => {
      box.style.display = "none";
    }, 6000);
  }

  appendDashboardChatMessage(sender, text) {
    const box = document.getElementById("ai-chat-history-box");
    if (!box || !text) return;

    const row = document.createElement("div");
    row.style.fontSize = "12px";
    row.style.lineHeight = "1.45";

    if (sender === "user") {
      row.style.color = "#00f0ff";
      row.innerHTML = `<strong>YOU:</strong> ${text}`;
    } else {
      row.style.color = "#00ff88";
      row.innerHTML = `<strong>ULTRON:</strong> ${text}`;
    }

    box.appendChild(row);
    box.scrollTop = box.scrollHeight;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  window.ultronDash = new UltronDashboard();
});
