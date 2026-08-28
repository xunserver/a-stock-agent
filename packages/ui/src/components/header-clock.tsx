import { useEffect, useState } from "react"

const TIMEZONE = "Asia/Shanghai"

function formatNow(now: Date) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: TIMEZONE,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(now)
}

export function HeaderClock() {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <time
      dateTime={now.toISOString()}
      className="text-muted-foreground text-xs tabular-nums"
      title="北京时间"
    >
      {formatNow(now)}
    </time>
  )
}
