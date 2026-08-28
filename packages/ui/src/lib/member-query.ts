import type { PoolMember } from "@/lib/api"
import { tickerFromCode } from "@/lib/ticker"

export function normalizeMemberQuery(query: string): string {
  return query.trim().toLowerCase()
}

function compactToken(value: string): string {
  return value.replace(/[\s.]+/g, "")
}

export function memberMatchesQuery(
  member: Pick<PoolMember, "code" | "name">,
  query: string
): boolean {
  const needle = normalizeMemberQuery(query)
  if (!needle) {
    return true
  }
  const code = member.code.toLowerCase()
  const ticker = tickerFromCode(member.code).toLowerCase()
  const name = (member.name ?? "").toLowerCase()
  if (
    code.includes(needle) ||
    ticker.includes(needle) ||
    name.includes(needle)
  ) {
    return true
  }
  const compactNeedle = compactToken(needle)
  if (!compactNeedle) {
    return false
  }
  return (
    compactToken(code).includes(compactNeedle) ||
    compactToken(ticker).includes(compactNeedle) ||
    compactToken(name).includes(compactNeedle)
  )
}

export function filterMembersByQuery<T extends Pick<PoolMember, "code" | "name">>(
  members: T[] | null,
  query: string
): T[] | null {
  if (!members || !normalizeMemberQuery(query)) {
    return members
  }
  return members.filter((member) => memberMatchesQuery(member, query))
}
