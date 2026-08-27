import { existsSync } from "node:fs"
import { join } from "node:path"
import { app, BrowserWindow, shell } from "electron"

function preloadScript(): string {
  const dir = join(import.meta.dirname, "../preload")
  for (const name of ["index.js", "index.mjs", "index.cjs"]) {
    const candidate = join(dir, name)
    if (existsSync(candidate)) {
      return candidate
    }
  }
  return join(dir, "index.js")
}

export function createMainWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: preloadScript(),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  win.on("ready-to-show", () => {
    win.show()
  })

  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: "deny" }
  })

  return win
}

export async function loadApp(win: BrowserWindow): Promise<void> {
  if (!app.isPackaged && process.env.ELECTRON_RENDERER_URL) {
    await win.loadURL(process.env.ELECTRON_RENDERER_URL)
    return
  }
  await win.loadFile(join(import.meta.dirname, "../renderer/index.html"))
}

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
}

export async function loadError(
  win: BrowserWindow,
  message: string
): Promise<void> {
  const html = `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <title>管控面</title>
    <style>
      body { font-family: sans-serif; padding: 48px; max-width: 40rem; color: #111; }
      h1 { font-size: 1.5rem; }
      p { white-space: pre-wrap; }
    </style>
  </head>
  <body>
    <h1>无法启动管控面</h1>
    <p>${escapeHtml(message)}</p>
  </body>
</html>`
  await win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`)
  if (!win.isVisible()) {
    win.show()
  }
}
