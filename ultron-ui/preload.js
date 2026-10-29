const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  setIgnoreMouseEvents: (ignore, options) => {
    ipcRenderer.send('set-ignore-mouse-events', ignore, options);
  },
  openDashboard: () => {
    ipcRenderer.send('open-dashboard');
  },
  closeDashboard: () => {
    ipcRenderer.send('close-dashboard');
  },
  quitApp: () => {
    ipcRenderer.send('quit-app');
  },
  onTriggerWake: (callback) => {
    ipcRenderer.on('trigger-wake', () => callback());
  },
  onToggleMuteFromTray: (callback) => {
    ipcRenderer.on('toggle-mute-from-tray', () => callback());
  },
  setWindowMode: (mode) => {
    ipcRenderer.send('set-window-mode', mode);
  },
  onWindowModeChanged: (callback) => {
    ipcRenderer.on('window-mode-changed', (event, isOnTop) => callback(isOnTop));
  },
  browseAppFile: () => ipcRenderer.invoke('browse-app-file')
});

