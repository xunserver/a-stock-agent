import { apiUrl, apiUrlWithQuery, requestJson } from "./http"
import { submitCommand, waitForJob, type Job } from "./jobs"

export type StockPoolRef = { id: string; name: string }
export type StockRow = {
  code: string
  ticker?: string
  name: string | null
  industry: string | null
  is_st: number
  is_suspended: number
  last_bar: string | null
  pools: StockPoolRef[]
}
export type StocksList = {
  count: number
  in_pool: number
  profile_filled: number
  stocks: StockRow[]
}
export type DailyBar = {
  trade_date: string
  open: number | null
  close: number | null
  high: number | null
  low: number | null
  volume: number | null
  amount: number | null
  pct_chg: number | null
  turnover: number | null
  amplitude: number | null
  change_amount: number | null
}
export type StockProfile = {
  code: string
  name: string | null
  industry: string | null
  region: string | null
  list_date: string | null
  total_shares: number | null
  float_shares: number | null
  total_mv: number | null
  float_mv: number | null
  latest_price: number | null
  pre_close: number | null
  avg_price: number | null
  high_limit: number | null
  low_limit: number | null
  volume_ratio: number | null
  outer_vol: number | null
  inner_vol: number | null
  pe_dyn: number | null
  pe_static: number | null
  pb: number | null
  eps: number | null
  bps: number | null
  roe: number | null
  revenue: number | null
  revenue_yoy: number | null
  net_profit: number | null
  net_profit_yoy: number | null
  gross_margin: number | null
  net_margin: number | null
  debt_ratio: number | null
  is_st: number
  is_suspended: number
  suspend_info: string | null
  updated_at: string | null
}
export type QuotesSummary = {
  adjust: string
  bars: number
  first: string | null
  last: string | null
  calendar_as_of: string | null
  missing_sessions: number
}
export type FinancialReport = {
  report_date: string
  report_type?: string | null
  notice_date?: string | null
  eps?: number | null
  bps?: number | null
  roe?: number | null
  revenue?: number | null
  revenue_yoy?: number | null
  net_profit?: number | null
  net_profit_yoy?: number | null
  gross_margin?: number | null
  net_margin?: number | null
  debt_ratio?: number | null
  updated_at?: string | null
}
export type FinancialSummary = { count: number; latest_report_date: string | null }
export type FinancialStatementSheet = "balance" | "profit" | "cashflow"
export type FinancialStatementSheetSummary = { count: number; latest_report_date: string | null }
export type FinancialStatementsSummary = Record<
  FinancialStatementSheet,
  FinancialStatementSheetSummary
>
export type FinancialStatementKeyItem = {
  key: string
  label: string
  value: number | string | null
  kind?: "amount" | "percent" | string
  yoy?: number | null
  qoq?: number | null
}
export type FinancialStatementDetail = {
  code: string
  ticker: string
  sheet: FinancialStatementSheet
  report_date: string
  report_type?: string | null
  notice_date?: string | null
  key_items: FinancialStatementKeyItem[]
  payload: Record<string, number | string>
  updated_at?: string | null
}
export type StockDetail = {
  code: string
  ticker: string
  profile: StockProfile
  pools?: StockPoolRef[]
  quotes_summary: QuotesSummary
  latest_bar: DailyBar | null
  bars: DailyBar[]
  bars_weekly?: DailyBar[]
  bars_yearly?: DailyBar[]
  financial_reports?: FinancialReport[]
  financial_summary?: FinancialSummary
  financial_statements_summary?: FinancialStatementsSummary
}
export type StockNewsItem = {
  title: string
  summary?: string
  published_at?: string
  source?: string
  url?: string
}
export type StockNews = { code: string; ticker: string; count: number; news: StockNewsItem[]; error?: string | null }
export type StockEventKind = "notices" | "research" | "block_trades" | "holder_changes"
export type StockEventItem = {
  title: string
  summary?: string
  published_at?: string
  source?: string
  url?: string
  extra?: Record<string, unknown>
}
export type StockEvents = { code: string; ticker: string; kind: StockEventKind; count: number; events: StockEventItem[]; error?: string | null }

export function queryStocks(): Promise<StocksList> {
  return requestJson<StocksList>(apiUrl("/api/stocks"))
}
export function queryStock(code: string): Promise<StockDetail> {
  return requestJson<StockDetail>(apiUrl(`/api/stocks/${encodeURIComponent(code)}`))
}
export function queryStockNews(code: string): Promise<StockNews> {
  return requestJson<StockNews>(apiUrlWithQuery(`/api/stocks/${encodeURIComponent(code)}/news`, { limit: 20 }))
}
export function queryStockEvents(code: string, kind: StockEventKind): Promise<StockEvents> {
  return requestJson<StockEvents>(apiUrlWithQuery(
    `/api/stocks/${encodeURIComponent(code)}/events/${encodeURIComponent(kind)}`,
    { limit: kind === "research" ? 20 : 50 }
  ))
}
export function queryFinancialDetail(
  code: string,
  options: { sheet: FinancialStatementSheet; reportDate: string }
): Promise<FinancialStatementDetail> {
  return requestJson<FinancialStatementDetail>(apiUrl(
    `/api/stocks/${encodeURIComponent(code)}/financial-statements/${encodeURIComponent(options.sheet)}/${encodeURIComponent(options.reportDate)}`
  ))
}
export function submitStockSync(codes: string[], options?: { withStatements?: boolean }): Promise<Job> {
  return submitCommand({ type: "stock.sync", codes, ...(options?.withStatements ? { with_statements: true } : {}) })
}
export async function addStockCodes(codes: string): Promise<Job> {
  return waitForJob(await submitCommand({ type: "stock.add", codes }))
}
export function addStockIndex(index: string): Promise<Job> {
  return submitCommand({ type: "stock.add", index, background: true })
}
export async function removeStockCodes(codes: string[]): Promise<Job> {
  return waitForJob(await submitCommand({ type: "stock.remove", codes }))
}
