const { app, BrowserWindow, Menu, Tray, nativeImage, ipcMain } = require('electron');
const path = require('path');
const { startOllama, startBackend, stopAll, getStatus } = require('./process-manager');

const isDev = !app.isPackaged;
let mainWindow;
let tray;
let isQuitting = false;

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForBackend(timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch('http://localhost:9147/health');
      if (res.ok) return true;
    } catch {
      // keep polling
    }
    await wait(1000);
  }
  return false;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
}

function createTray() {
  tray = new Tray(nativeImage.createEmpty());
  tray.setToolTip('Forge AI');

  const menu = Menu.buildFromTemplate([
    { label: 'Show Forge', click: () => { mainWindow.show(); mainWindow.focus(); } },
    {
      label: 'Status',
      submenu: [
        { label: 'All systems running', enabled: false },
      ],
    },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true;
        stopAll();
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(menu);
  tray.on('click', () => {
    mainWindow.show();
    mainWindow.focus();
  });
}

async function loadApp() {
  const url = 'http://localhost:9147';
  if (isDev) {
    await mainWindow.loadURL(url);
  } else {
    await mainWindow.loadURL(url);
  }
}

app.whenReady().then(async () => {
  ipcMain.handle('forge:getStatus', () => getStatus());

  createWindow();
  createTray();

  await startOllama();
  await startBackend();
  await waitForBackend();
  await loadApp();
});

app.on('before-quit', () => {
  isQuitting = true;
  stopAll();
});

app.on('window-all-closed', (event) => {
  event.preventDefault();
});
