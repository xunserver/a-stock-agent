import { useEffect, useState } from "react"

import type { UpdateStatus } from "./env"

export function UpdateBanner() {
  const [status, setStatus] = useState<UpdateStatus | null>(null)

  useEffect(() => {
    const api = window.desktop
    if (!api?.onUpdateStatus) {
      return
    }
    return api.onUpdateStatus(setStatus)
  }, [])

  if (!status) {
    return null
  }

  if (status.type === "available") {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          padding: "8px 16px",
          background: "#0f172a",
          color: "#f8fafc",
          fontSize: 13,
        }}
      >
        <span>发现新版本 {status.version}</span>
        <button
          type="button"
          style={{
            border: "1px solid #94a3b8",
            background: "transparent",
            color: "inherit",
            padding: "4px 10px",
            cursor: "pointer",
          }}
          onClick={() => {
            void window.desktop?.downloadUpdate()
          }}
        >
          下载更新
        </button>
      </div>
    )
  }

  if (status.type === "progress") {
    return (
      <div
        style={{
          padding: "8px 16px",
          background: "#0f172a",
          color: "#f8fafc",
          fontSize: 13,
        }}
      >
        正在下载更新… {status.percent.toFixed(0)}%
      </div>
    )
  }

  if (status.type === "downloaded") {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          padding: "8px 16px",
          background: "#0f172a",
          color: "#f8fafc",
          fontSize: 13,
        }}
      >
        <span>版本 {status.version} 已下载，可立即安装</span>
        <button
          type="button"
          style={{
            border: "1px solid #94a3b8",
            background: "transparent",
            color: "inherit",
            padding: "4px 10px",
            cursor: "pointer",
          }}
          onClick={() => {
            void window.desktop?.installUpdate()
          }}
        >
          立即安装
        </button>
      </div>
    )
  }

  if (status.type === "error") {
    return (
      <div
        style={{
          padding: "8px 16px",
          background: "#450a0a",
          color: "#fecaca",
          fontSize: 13,
        }}
        title={status.message}
      >
        检查更新失败
      </div>
    )
  }

  return null
}
