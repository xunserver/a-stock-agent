import { BrowserWindow, app, dialog, ipcMain } from "electron"
import { autoUpdater } from "electron-updater"

export type UpdateStatus =
  | { type: "checking" }
  | { type: "available"; version: string }
  | { type: "not-available"; version: string }
  | { type: "downloaded"; version: string }
  | { type: "error"; message: string }
  | { type: "progress"; percent: number }

function broadcast(status: UpdateStatus): void {
  for (const win of BrowserWindow.getAllWindows()) {
    win.webContents.send("desktop:update-status", status)
  }
}

let started = false

export function initAutoUpdater(): void {
  if (started) {
    return
  }
  started = true

  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  autoUpdater.on("checking-for-update", () => {
    broadcast({ type: "checking" })
  })

  autoUpdater.on("update-available", (info) => {
    broadcast({ type: "available", version: info.version })
    void (async () => {
      const options = {
        type: "info" as const,
        title: "发现新版本",
        message: `有新版本 ${info.version} 可用，是否下载？`,
        buttons: ["下载更新", "稍后"],
        defaultId: 0,
        cancelId: 1,
      }
      const win = BrowserWindow.getFocusedWindow()
      const result = win
        ? await dialog.showMessageBox(win, options)
        : await dialog.showMessageBox(options)
      if (result.response === 0) {
        await autoUpdater.downloadUpdate()
      }
    })()
  })

  autoUpdater.on("update-not-available", (info) => {
    broadcast({ type: "not-available", version: info.version })
  })

  autoUpdater.on("download-progress", (progress) => {
    broadcast({ type: "progress", percent: progress.percent })
  })

  autoUpdater.on("update-downloaded", (info) => {
    broadcast({ type: "downloaded", version: info.version })
    void (async () => {
      const options = {
        type: "info" as const,
        title: "更新已就绪",
        message: `版本 ${info.version} 已下载完成，是否立即安装并重启？`,
        buttons: ["立即安装", "稍后"],
        defaultId: 0,
        cancelId: 1,
      }
      const win = BrowserWindow.getFocusedWindow()
      const result = win
        ? await dialog.showMessageBox(win, options)
        : await dialog.showMessageBox(options)
      if (result.response === 0) {
        autoUpdater.quitAndInstall(false, true)
      }
    })()
  })

  autoUpdater.on("error", (error) => {
    broadcast({
      type: "error",
      message: error instanceof Error ? error.message : String(error),
    })
  })

  ipcMain.handle("desktop:check-for-updates", async () => {
    return autoUpdater.checkForUpdates()
  })

  ipcMain.handle("desktop:download-update", async () => {
    return autoUpdater.downloadUpdate()
  })

  ipcMain.handle("desktop:install-update", () => {
    autoUpdater.quitAndInstall(false, true)
  })

  ipcMain.handle("desktop:get-version", () => {
    return app.getVersion()
  })

  void autoUpdater.checkForUpdates().catch((error: unknown) => {
    broadcast({
      type: "error",
      message: error instanceof Error ? error.message : String(error),
    })
  })
}
