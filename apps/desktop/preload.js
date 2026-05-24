const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('forgeAPI', {
  getStatus: () => ipcRenderer.invoke('forge:getStatus'),
});
