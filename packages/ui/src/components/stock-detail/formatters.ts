export function fmtTimestamp(value: string | null | undefined): string | null {
  if (!value) return null
  return value.replace("T", " ").replace(/\.\d+/, "")
}

export function fmtPrice(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "—" : value.toFixed(2)
}

export function fmtPct(
  value: number | null | undefined,
  signed = true
): string {
  if (value == null || !Number.isFinite(value)) return "—"
  return `${signed && value > 0 ? "+" : ""}${value.toFixed(2)}%`
}

export function fmtNum(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—"
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(2)}万`
  return value.toFixed(2)
}

export function fmtRatio(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "—" : value.toFixed(2)
}
