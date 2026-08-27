import { type ReactNode } from "react"

import { useStockDetail } from "@/components/stock-detail-provider"
import { Button } from "@/components/ui/button"
import { normalizeStockCode, tickerFromCode } from "@/lib/ticker"
import { cn } from "@/lib/utils"

export function TickerLink({
  code,
  children,
  className,
}: {
  code: string
  children?: ReactNode
  className?: string
}) {
  const { openStock } = useStockDetail()
  const normalized = normalizeStockCode(code)
  if (!normalized) {
    return null
  }
  return (
    <Button
      type="button"
      variant="link"
      className={cn("h-auto px-0 font-mono", className)}
      onClick={(event) => {
        event.preventDefault()
        event.stopPropagation()
        openStock(normalized)
      }}
    >
      {children ?? tickerFromCode(normalized)}
    </Button>
  )
}
