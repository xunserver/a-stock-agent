export const WEEKDAY_LABELS = ["日", "一", "二", "三", "四", "五", "六"] as const

export type MonthCell = {
  date: string
  day: number
  inMonth: boolean
}

function pad2(value: number) {
  return String(value).padStart(2, "0")
}

export function isoDate(year: number, month: number, day: number): string {
  return `${year}-${pad2(month)}-${pad2(day)}`
}

export function shiftMonth(
  year: number,
  month: number,
  delta: number
): { year: number; month: number } {
  const next = month + delta
  if (next < 1) {
    return { year: year - 1, month: 12 }
  }
  if (next > 12) {
    return { year: year + 1, month: 1 }
  }
  return { year, month: next }
}

function daysInMonth(year: number, month: number) {
  return new Date(year, month, 0).getDate()
}

function weekdayIndex(year: number, month: number, day: number) {
  return new Date(year, month - 1, day).getDay()
}

export function weekdayLabel(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number)
  return `周${WEEKDAY_LABELS[weekdayIndex(year, month, day)]}`
}

export function monthGrid(year: number, month: number): MonthCell[] {
  const count = daysInMonth(year, month)
  const lead = weekdayIndex(year, month, 1)
  const cells: MonthCell[] = []
  if (lead > 0) {
    const prev = shiftMonth(year, month, -1)
    const prevCount = daysInMonth(prev.year, prev.month)
    for (let index = lead - 1; index >= 0; index--) {
      const day = prevCount - index
      cells.push({
        date: isoDate(prev.year, prev.month, day),
        day,
        inMonth: false,
      })
    }
  }
  for (let day = 1; day <= count; day++) {
    cells.push({
      date: isoDate(year, month, day),
      day,
      inMonth: true,
    })
  }
  const next = shiftMonth(year, month, 1)
  let nextDay = 1
  while (cells.length % 7 !== 0) {
    cells.push({
      date: isoDate(next.year, next.month, nextDay),
      day: nextDay,
      inMonth: false,
    })
    nextDay += 1
  }
  return cells
}
