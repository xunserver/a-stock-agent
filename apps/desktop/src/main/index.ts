import { app, BrowserWindow } from "electron"

import { startCore, stopCore } from "./core-process"
import { initAutoUpdater } from "./updater"
import { createMainWindow, loadApp, loadError } from "./window"

let quitting = false

async function boot(): Promise<void> {
  const win = createMainWindow()
  try {
    await startCore()
    await loadApp(win)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    await loadError(win, message)
  }
}

void app.whenReady().then(() => {
  void boot()
  if (app.isPackaged) {
    initAutoUpdater()
  }
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      void boot()
    }
  })
})

app.on("window-all-closed", () => {
  app.quit()
})

app.on("before-quit", (event) => {
  if (quitting) {
    return
  }
  event.preventDefault()
  quitting = true
  void stopCore().finally(() => {
    app.quit()
  })
})
