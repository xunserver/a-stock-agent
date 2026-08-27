const SUFFIX_RE = /\.(SZ|SS|SH|BJ)$/i
const TICKER_RE = /^(\d{6})(?:\.(SZ|SS|SH|BJ))?$/i

export function normalizeStockCode(value: string): string {
  const text = value.trim().toUpperCase()
  const match = text.match(TICKER_RE)
  if (match) {
    return match[1]
  }
  return text.replace(SUFFIX_RE, "")
}

export function tickerFromCode(code: string): string {
  const normalized = normalizeStockCode(code)
  if (normalized.startsWith("6") || normalized.startsWith("9") || normalized.startsWith("5")) {
    return `${normalized}.SS`
  }
  if (normalized.startsWith("4") || normalized.startsWith("8")) {
    return `${normalized}.BJ`
  }
  return `${normalized}.SZ`
}
