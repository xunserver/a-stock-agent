/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import { StockDetailDialog } from "@/components/stock-detail-dialog"
import { normalizeStockCode } from "@/lib/ticker"

type StockDetailContextValue = {
  openStock: (code: string) => void
  code: string | null
  closeStock: () => void
}

const StockDetailContext = createContext<StockDetailContextValue | null>(null)

export function StockDetailProvider({ children }: { children: ReactNode }) {
  const [code, setCode] = useState<string | null>(null)
  const openStock = useCallback((raw: string) => {
    const next = normalizeStockCode(raw)
    if (next) {
      setCode(next)
    }
  }, [])
  const value = useMemo(
    () => ({ openStock, code, closeStock: () => setCode(null) }),
    [openStock, code]
  )
  return (
    <StockDetailContext.Provider value={value}>
      {children}
    </StockDetailContext.Provider>
  )
}

export function StockDetailDialogHost() {
  const { code, closeStock } = useStockDetail()
  return (
    <StockDetailDialog
      code={code}
      onOpenChange={(open) => {
        if (!open) closeStock()
      }}
    />
  )
}

export function useStockDetail() {
  const context = useContext(StockDetailContext)
  if (!context) {
    throw new Error("useStockDetail 需要放在 StockDetailProvider 里")
  }
  return context
}
