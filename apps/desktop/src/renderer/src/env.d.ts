/// <reference types="vite/client" />

declare module "@astock/ui/styles.css"

export type UpdateStatus =
  | { type: "checking" }
  | { type: "available"; version: string }
  | { type: "not-available"; version: string }
  | { type: "downloaded"; version: string }
  | { type: "error"; message: string }
  | { type: "progress"; percent: number }

export type DesktopApi = {
  platform: string
  getVersion: () => Promise<string>
  checkForUpdates: () => Promise<unknown>
  downloadUpdate: () => Promise<unknown>
  installUpdate: () => Promise<void>
  onUpdateStatus: (listener: (status: UpdateStatus) => void) => () => void
}

declare global {
  interface Window {
    desktop?: DesktopApi
  }
}

export {}
