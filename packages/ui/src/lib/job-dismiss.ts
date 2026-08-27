const DISMISSED_JOBS_KEY = "astock.job-dismissed"

export function readDismissedJobs(): Set<string> {
  if (typeof window === "undefined") return new Set()
  try {
    const value: unknown = JSON.parse(
      window.sessionStorage.getItem(DISMISSED_JOBS_KEY) ?? "[]"
    )
    return new Set(
      Array.isArray(value)
        ? value.filter((item): item is string => typeof item === "string")
        : []
    )
  } catch {
    return new Set()
  }
}

export function writeDismissedJobs(ids: ReadonlySet<string>) {
  if (typeof window === "undefined") return
  window.sessionStorage.setItem(
    DISMISSED_JOBS_KEY,
    JSON.stringify([...ids].slice(-100))
  )
}
