/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  lazy,
  Suspense,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import { normalizeStockCode } from "@/lib/ticker"

const StockDetailDialog = lazy(() =>
  import("@/components/stock-detail-dialog").then((module) => ({
    default: module.StockDetailDialog,
  }))
)

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
  if (!code) return null
  return (
    <Suspense fallback={null}>
      <StockDetailDialog
        code={code}
        onOpenChange={(open) => {
          if (!open) closeStock()
        }}
      />
    </Suspense>
  )
}

export function useStockDetail() {
  const context = useContext(StockDetailContext)
  if (!context) {
    throw new Error("useStockDetail 需要放在 StockDetailProvider 里")
  }
  return context
}
