import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron"

export type UpdateStatus =
  | { type: "checking" }
  | { type: "available"; version: string }
  | { type: "not-available"; version: string }
  | { type: "downloaded"; version: string }
  | { type: "error"; message: string }
  | { type: "progress"; percent: number }

const desktop = {
  platform: process.platform,
  getVersion: (): Promise<string> => ipcRenderer.invoke("desktop:get-version"),
  checkForUpdates: (): Promise<unknown> =>
    ipcRenderer.invoke("desktop:check-for-updates"),
  downloadUpdate: (): Promise<unknown> =>
    ipcRenderer.invoke("desktop:download-update"),
  installUpdate: (): Promise<void> =>
    ipcRenderer.invoke("desktop:install-update"),
  onUpdateStatus: (listener: (status: UpdateStatus) => void): (() => void) => {
    const handler = (_event: IpcRendererEvent, status: UpdateStatus) => {
      listener(status)
    }
    ipcRenderer.on("desktop:update-status", handler)
    return () => {
      ipcRenderer.removeListener("desktop:update-status", handler)
    }
  },
}

contextBridge.exposeInMainWorld("desktop", desktop)
