import type { PoolMember } from "@/lib/api"

export type QuoteFilter = "all" | "sync"

const QUOTE_FILTERS = new Set<QuoteFilter>(["all", "sync"])

export function isQuoteFilter(value: string | undefined): value is QuoteFilter {
  return value != null && QUOTE_FILTERS.has(value as QuoteFilter)
}

export function nextQuoteFilter(
  next: readonly string[],
  current: QuoteFilter
): QuoteFilter | null {
  const valid = next.filter(isQuoteFilter)
  if (valid.length === 0) {
    return null
  }
  return valid.find((item) => item !== current) ?? valid[0]
}

export function memberNeedsSync(member: Pick<PoolMember, "needs_sync" | "quote_plan">): boolean {
  if (member.needs_sync != null) {
    return Boolean(member.needs_sync)
  }
  return member.quote_plan === "full" || member.quote_plan === "fill"
}

export function filterMembersByQuotePlan<
  T extends Pick<PoolMember, "needs_sync" | "quote_plan">,
>(members: T[] | null, quoteFilter: QuoteFilter): T[] | null {
  if (!members || quoteFilter === "all") {
    return members
  }
  return members.filter((member) => memberNeedsSync(member))
}
