export const API_BASE = import.meta.env.VITE_API_BASE ?? ""

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}

/** Builds query strings consistently so feature routes never receive raw input. */
export function apiUrlWithQuery(
  path: string,
  params: Record<string, string | number | boolean | undefined>
): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value))
  }
  return apiUrl(`${path}${query.size > 0 ? `?${query.toString()}` : ""}`)
}

export function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

export async function readError(response: Response): Promise<string> {
  const body: unknown = await response.json().catch(() => null)
  if (isJsonObject(body)) {
    if (typeof body.error === "string") return body.error
    if (isJsonObject(body.error) && typeof body.error.message === "string") {
      return body.error.message
    }
    if (typeof body.detail === "string") return body.detail
  }
  return `HTTP ${response.status}`
}

/** The sole HTTP boundary for JSON APIs. Feature clients only provide paths and DTOs. */
export async function requestJson<T>(
  url: string,
  init?: RequestInit
): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set("Accept", "application/json")
  const response = await fetch(url, { ...init, headers })
  if (!response.ok) throw new Error(await readError(response))
  return (await response.json()) as T
}
