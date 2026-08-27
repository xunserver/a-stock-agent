import { existsSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { createConnection } from "node:net"
import { spawn, type ChildProcess } from "node:child_process"
import { app } from "electron"

export const CORE_HOST = "127.0.0.1"
export const CORE_PORT = 8787
export const CORE_ORIGIN = `http://${CORE_HOST}:${CORE_PORT}`
const HEALTH_URL = `${CORE_ORIGIN}/api/health`
const HEALTH_TIMEOUT_MS = 30_000
const STOP_TIMEOUT_MS = 5_000

let child: ChildProcess | null = null

export function findRepoRoot(): string {
  const starts = [process.cwd(), app.getAppPath(), import.meta.dirname]
  for (const start of starts) {
    let dir = resolve(start)
    while (true) {
      if (existsSync(join(dir, ".astock-root"))) {
        return dir
      }
      const parent = dirname(dir)
      if (parent === dir) {
        break
      }
      dir = parent
    }
  }
  throw new Error("找不到仓库根目录（缺少 .astock-root）")
}

function isPortOpen(host: string, port: number): Promise<boolean> {
  return new Promise((resolveOpen) => {
    const socket = createConnection({ host, port })
    socket.setTimeout(500)
    socket.once("connect", () => {
      socket.destroy()
      resolveOpen(true)
    })
    socket.once("timeout", () => {
      socket.destroy()
      resolveOpen(false)
    })
    socket.once("error", () => {
      resolveOpen(false)
    })
  })
}

async function isOurHealth(): Promise<boolean> {
  try {
    const response = await fetch(HEALTH_URL)
    if (!response.ok) {
      return false
    }
    const body: unknown = await response.json()
    return (
      typeof body === "object" &&
      body !== null &&
      "ok" in body &&
      (body as { ok: unknown }).ok === true
    )
  } catch {
    return false
  }
}

async function waitForHealth(timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await isOurHealth()) {
      return
    }
    await new Promise((r) => setTimeout(r, 200))
  }
  throw new Error(`core 在 ${timeoutMs}ms 内没有通过 /api/health`)
}

export async function startCore(): Promise<void> {
  if (child) {
    return
  }
  if (await isPortOpen(CORE_HOST, CORE_PORT)) {
    if (await isOurHealth()) {
      throw new Error(
        `端口 ${CORE_PORT} 已被占用：已有 core 在跑。请先关掉它再启动桌面端。`
      )
    }
    throw new Error(`端口 ${CORE_PORT} 已被其他程序占用。`)
  }

  const repoRoot = findRepoRoot()
  const coreDir = join(repoRoot, "apps/control-plane/core")
  const spawned = spawn(
    "uv",
    [
      "--directory",
      coreDir,
      "run",
      "python",
      "-m",
      "astock_control",
      "--host",
      CORE_HOST,
      "--port",
      String(CORE_PORT),
    ],
    {
      cwd: repoRoot,
      stdio: ["ignore", "pipe", "pipe"],
      detached: true,
      env: process.env,
    }
  )
  child = spawned
  spawned.stdout?.on("data", (buf: Buffer) => {
    process.stdout.write(buf)
  })
  spawned.stderr?.on("data", (buf: Buffer) => {
    process.stderr.write(buf)
  })

  let settled = false
  const spawnError = new Promise<never>((_, reject) => {
    spawned.once("error", (err) => {
      if (settled) {
        return
      }
      reject(new Error(`无法启动 core（找不到 uv？）: ${err.message}`))
    })
    spawned.once("exit", (code, signal) => {
      if (settled) {
        return
      }
      reject(new Error(`core 提前退出 code=${code} signal=${signal}`))
    })
  })

  try {
    await Promise.race([waitForHealth(HEALTH_TIMEOUT_MS), spawnError])
    settled = true
  } catch (error) {
    settled = true
    await stopCore()
    throw error
  }
}

export async function stopCore(): Promise<void> {
  const current = child
  child = null
  if (current?.pid == null) {
    return
  }
  const pid = current.pid
  const exited = new Promise<void>((resolve) => {
    current.once("exit", () => resolve())
  })
  try {
    process.kill(-pid, "SIGTERM")
  } catch {
    current.kill("SIGTERM")
  }
  await Promise.race([
    exited,
    new Promise<void>((resolve) => {
      setTimeout(() => {
        try {
          process.kill(-pid, "SIGKILL")
        } catch {
          current.kill("SIGKILL")
        }
        resolve()
      }, STOP_TIMEOUT_MS)
    }),
  ])
}
