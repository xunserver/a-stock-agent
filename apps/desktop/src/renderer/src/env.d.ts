/// <reference types="vite/client" />

declare module "@astock/ui/styles.css"

export type DesktopApi = {
  platform: string
}

declare global {
  interface Window {
    desktop?: DesktopApi
  }
}

export {}
