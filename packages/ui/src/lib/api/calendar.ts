import { apiUrl, apiUrlWithQuery, requestJson } from "./http"

export type CalendarMarket = {
  id: string
  title: string
  status: "active" | "planned" | string
  count: number
  first: string | null
  last: string | null
}
export type CalendarMarkets = { count: number; markets: CalendarMarket[] }
export type CalendarDay = { date: string; is_trading: boolean }
export type CalendarMonth = {
  market: string
  title: string
  status: string
  year: number
  month: number
  start: string
  end: string
  trading_days: number
  days: CalendarDay[]
  today: string
  today_is_trading: boolean
  trade_date: string | null
  coverage: { count: number; first: string | null; last: string | null }
}
export type CalendarSession = { label: string; start: string; end: string }
export type CalendarOverviewMarket = {
  id: string
  title: string
  status: string
  timezone: string
  today: string
  today_is_trading: boolean
  trade_date: string | null
  in_session: boolean
  has_calendar: boolean
  sessions: CalendarSession[]
  sessions_note: string | null
}
export type CalendarOverview = { markets: CalendarOverviewMarket[] }
export type CalendarGridMarket = {
  id: string
  title: string
  badge: string
  status: string
  timezone: string
  today: string
  in_session: boolean
  has_calendar: boolean
  sessions: CalendarSession[]
  sessions_note: string | null
}
export type CalendarGridDay = { date: string; markets: string[] }
export type CalendarGrid = {
  year: number
  month: number
  start: string
  end: string
  today: string
  days: CalendarGridDay[]
  markets: CalendarGridMarket[]
}

export function queryCalendarMarkets(): Promise<CalendarMarkets> {
  return requestJson<CalendarMarkets>(apiUrl("/api/calendars/markets"))
}
export function queryCalendarOverview(): Promise<CalendarOverview> {
  return requestJson<CalendarOverview>(apiUrl("/api/calendars/overview"))
}
export function queryCalendarMonth(options: {
  market: string
  year: number
  month: number
}): Promise<CalendarMonth> {
  return requestJson<CalendarMonth>(
    apiUrl(`/api/calendars/${encodeURIComponent(options.market)}/${encodeURIComponent(String(options.year))}/${encodeURIComponent(String(options.month))}`)
  )
}
export function queryCalendarGrid(options?: { year: number; month: number }): Promise<CalendarGrid> {
  return requestJson<CalendarGrid>(apiUrlWithQuery("/api/calendars/month", {
    year: options?.year,
    month: options?.month,
  }))
}
