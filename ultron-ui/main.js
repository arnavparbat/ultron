const { app, BrowserWindow, ipcMain, Tray, Menu, screen, nativeImage, dialog } = require('electron');
const path = require('path');

// Disable redundant shader & HTTP disk caching to prevent "Unable to create cache: Access is denied" errors
app.commandLine.appendSwitch('disable-gpu-shader-disk-cache');
app.commandLine.appendSwitch('disable-http-cache');

// Enforce single-instance execution to avoid multi-process cache conflicts
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  console.log('[Ultron UI] Another instance is already running. Exiting redundant process.');
  app.quit();
  process.exit(0);
}

let overlayWindow = null;
let dashboardWindow = null;
let tray = null;
let isMuted = false;

app.on('second-instance', () => {
  if (overlayWindow) {
    if (!overlayWindow.isVisible()) overlayWindow.show();
    overlayWindow.focus();
  }
});

function getAppIcon() {
  const icoPath = path.join(__dirname, 'assets', 'icon.ico');
  const pngPath = path.join(__dirname, 'assets', 'icon.png');
  if (process.platform === 'win32' && require('fs').existsSync(icoPath)) {
    return nativeImage.createFromPath(icoPath);
  }
  return nativeImage.createFromPath(pngPath);
}

function createTrayIcon() {
  const iconPath = path.join(__dirname, 'assets', 'icon.png');
  if (require('fs').existsSync(iconPath)) {
    return nativeImage.createFromPath(iconPath).resize({ width: 24, height: 24 });
  }
  // Create a clean neon cyan circle tray icon if no file exists
  const canvasSize = 32;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${canvasSize}" height="${canvasSize}" viewBox="0 0 32 32">
      <circle cx="16" cy="16" r="13" fill="#090d16" stroke="#00f0ff" stroke-width="2.5"/>
      <circle cx="16" cy="16" r="6" fill="#00f0ff"/>
      <line x1="16" y1="3" x2="16" y2="29" stroke="#00f0ff" stroke-width="1.5" stroke-dasharray="2,2"/>
      <line x1="3" y1="16" x2="29" y2="16" stroke="#00f0ff" stroke-width="1.5" stroke-dasharray="2,2"/>
    </svg>
  `;
  return nativeImage.createFromBuffer(Buffer.from(svg));
}

let isAlwaysOnTopMode = false;

function setOverlayMode(mode) {
  if (!overlayWindow) return;
  if (mode === 'always-on-top') {
    isAlwaysOnTopMode = true;
    overlayWindow.setAlwaysOnTop(true, 'screen-saver');
    overlayWindow.moveTop();
    overlayWindow.show();
    console.log('[Ultron UI] Window mode -> ALWAYS-ON-TOP ("Come to me")');
  } else {
    isAlwaysOnTopMode = false;
    overlayWindow.setAlwaysOnTop(false);
    console.log('[Ultron UI] Window mode -> DESKTOP (Only on desktop)');
  }
  if (overlayWindow.webContents) {
    overlayWindow.webContents.send('window-mode-changed', isAlwaysOnTopMode);
  }
}

function createOverlayWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;

  const winWidth = 380;
  const winHeight = 540;
  const x = screenWidth - winWidth - 24;
  const y = 32;

  overlayWindow = new BrowserWindow({
    width: winWidth,
    height: winHeight,
    x: x,
    y: y,
    frame: false,
    transparent: true,
    alwaysOnTop: false, // Default: ONLY ON DESKTOP (behind active windows)
    skipTaskbar: true,
    resizable: false, 
    icon: getAppIcon(),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  overlayWindow.loadFile(path.join(__dirname, 'overlay', 'index.html'));

  // Default non-blocking click-through
  overlayWindow.setIgnoreMouseEvents(true, { forward: true });

  overlayWindow.on('closed', () => {
    overlayWindow = null;
  });
}

function createDashboardWindow() {
  if (dashboardWindow) {
    dashboardWindow.show();
    dashboardWindow.focus();
    return;
  }

  dashboardWindow = new BrowserWindow({
    width: 980,
    height: 720,
    minWidth: 800,
    minHeight: 600, icon: getAppIcon(),
    title: "Ultron System Dashboard & Screen Time",
    backgroundColor: '#070a0f',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  dashboardWindow.loadFile(path.join(__dirname, 'dashboard', 'index.html'));

  dashboardWindow.on('closed', () => {
    dashboardWindow = null;
  });
}

function setupTray() {
  const icon = createTrayIcon();
  tray = new Tray(icon);
  tray.setToolTip('Ultron AI Voice Assistant');

  const updateMenu = () => {
    const contextMenu = Menu.buildFromTemplate([
      { label: 'ULTRON AI — ONLINE', enabled: false },
      { type: 'separator' },
      {
        label: 'Open Dashboard',
        click: () => createDashboardWindow()
      },
      {
        label: 'Trigger Voice Wake ("Hey Ultron")',
        click: () => {
          if (overlayWindow) {
            overlayWindow.webContents.send('trigger-wake');
          }
        }
      },
      {
        label: isMuted ? 'Unmute Microphone' : 'Mute Microphone',
        click: () => {
          isMuted = !isMuted;
          if (overlayWindow) {
            overlayWindow.webContents.send('toggle-mute-from-tray');
          }
          updateMenu();
        }
      },
      {
        label: isAlwaysOnTopMode ? 'Mode: Always on Top' : 'Mode: Desktop Only',
        click: () => {
          setOverlayMode(isAlwaysOnTopMode ? 'desktop' : 'always-on-top');
          updateMenu();
        }
      },
      {
        label: 'Toggle Sphere Overlay',
        click: () => {
          if (overlayWindow) {
            if (overlayWindow.isVisible()) overlayWindow.hide();
            else overlayWindow.show();
          }
        }
      },
      { type: 'separator' },
      {
        label: 'Quit Ultron',
        click: () => {
          app.isQuitting = true;
          app.quit();
        }
      }
    ]);
    tray.setContextMenu(contextMenu);
  };

  updateMenu();
  tray.on('double-click', () => createDashboardWindow());
}

app.whenReady().then(() => {
  createOverlayWindow();
  setupTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createOverlayWindow();
    }
  });
});

// IPC Event Handlers
ipcMain.on('set-ignore-mouse-events', (event, ignore, options) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win && win === overlayWindow) {
    win.setIgnoreMouseEvents(ignore, options || { forward: true });
  }
});

ipcMain.on('set-window-mode', (event, mode) => {
  setOverlayMode(mode);
});

ipcMain.on('open-dashboard', () => {
  createDashboardWindow();
});

ipcMain.on('close-dashboard', () => {
  if (dashboardWindow) {
    dashboardWindow.close();
  }
});

ipcMain.on('quit-app', () => {
  app.isQuitting = true;
  app.quit();
});

ipcMain.handle('browse-app-file', async () => {
  try {
    const targetWin = dashboardWindow || overlayWindow;
    const result = await dialog.showOpenDialog(targetWin, {
      title: 'Select Application or Executable',
      properties: ['openFile'],
      filters: [
        { name: 'Applications & Executables (*.exe, *.lnk, *.bat, *.cmd, *.url)', extensions: ['exe', 'lnk', 'bat', 'cmd', 'url'] },
        { name: 'All Files (*.*)', extensions: ['*'] }
      ]
    });
    if (!result.canceled && result.filePaths && result.filePaths.length > 0) {
      return result.filePaths[0];
    }
    return null;
  } catch (err) {
    console.error('[Ultron UI] Error showing open dialog:', err);
    return null;
  }
});


app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    // Keep app running silently in tray
  }
});

