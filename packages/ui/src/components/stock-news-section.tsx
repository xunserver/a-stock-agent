import { useEffect, useState } from "react"
import { NewspaperIcon } from "lucide-react"

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { queryStockNews, type StockNewsItem } from "@/lib/api"
import { cn } from "@/lib/utils"

export function StockNewsSection({
  code,
  reloadKey = 0,
  className,
  showHeading = true,
}: {
  code: string
  reloadKey?: number
  className?: string
  showHeading?: boolean
}) {
  const [items, setItems] = useState<StockNewsItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setItems([])
    void (async () => {
      try {
        const next = await queryStockNews(code)
        if (cancelled) {
          return
        }
        setItems(next.news ?? [])
        setError(next.error || null)
      } catch (err: unknown) {
        if (!cancelled) {
          setItems([])
          setError(err instanceof Error ? err.message : "新闻暂时不可用")
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [code, reloadKey])

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {showHeading ? (
        <p className="text-[11px] font-medium text-muted-foreground">新闻</p>
      ) : null}
      {loading ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : items.length === 0 ? (
        <Empty className="gap-2 border border-dashed p-4">
          <EmptyHeader className="gap-1">
            <EmptyMedia variant="icon">
              <NewspaperIcon />
            </EmptyMedia>
            <EmptyTitle>暂无相关新闻</EmptyTitle>
            <EmptyDescription>
              {error || "东方财富暂时没有这只股票的新闻。"}
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <ul className="flex flex-col">
          {items.map((item, index) => (
            <NewsRow key={`${item.url || item.title}-${index}`} item={item} />
          ))}
        </ul>
      )}
    </div>
  )
}

function NewsRow({ item }: { item: StockNewsItem }) {
  const meta = [item.source, item.published_at].filter(Boolean).join(" · ")
  const title = item.title || "未命名新闻"
  return (
    <li className="border-b border-border py-2 last:border-b-0">
      <div className="flex flex-col gap-0.5">
        <div className="flex items-baseline justify-between gap-3">
          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noreferrer"
              className="min-w-0 flex-1 truncate text-sm font-medium text-foreground hover:underline"
            >
              {title}
            </a>
          ) : (
            <p className="min-w-0 flex-1 truncate text-sm font-medium">
              {title}
            </p>
          )}
          {meta ? (
            <p className="shrink-0 text-[11px] text-muted-foreground">{meta}</p>
          ) : null}
        </div>
        {item.summary ? (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {item.summary}
          </p>
        ) : null}
      </div>
    </li>
  )
}
