import { useEffect, useState } from "react"
import {
  FileTextIcon,
  LandmarkIcon,
  NewspaperIcon,
  ScrollTextIcon,
  UsersIcon,
} from "lucide-react"

import { StockNewsSection } from "@/components/stock-news-section"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  queryStockEvents,
  type StockEventItem,
  type StockEventKind,
} from "@/lib/api"
import { cn } from "@/lib/utils"

type TabId = "news" | StockEventKind

const TABS: { id: TabId; label: string }[] = [
  { id: "news", label: "新闻" },
  { id: "notices", label: "公告" },
  { id: "research", label: "研报" },
  { id: "block_trades", label: "大宗交易" },
  { id: "holder_changes", label: "股东变更" },
]

const EMPTY_COPY: Record<
  StockEventKind,
  { title: string; description: string; icon: typeof NewspaperIcon }
> = {
  notices: {
    title: "暂无公告",
    description: "近一年没有查到这只股票的公告。",
    icon: ScrollTextIcon,
  },
  research: {
    title: "暂无研报",
    description: "暂时没有这只股票的研报。",
    icon: FileTextIcon,
  },
  block_trades: {
    title: "暂无大宗交易",
    description: "近 90 天没有这只股票的大宗成交。",
    icon: LandmarkIcon,
  },
  holder_changes: {
    title: "暂无股东变更",
    description: "暂时没有董监高持股变动记录。",
    icon: UsersIcon,
  },
}

export function StockEventsTabs({
  code,
  reloadKey = 0,
  className,
}: {
  code: string
  reloadKey?: number
  className?: string
}) {
  const [tab, setTab] = useState<TabId>("news")

  return (
    <Tabs
      value={tab}
      onValueChange={(value) => {
        if (typeof value === "string") {
          setTab(value as TabId)
        }
      }}
      className={cn("flex flex-col gap-2", className)}
    >
      <TabsList variant="line" className="h-auto w-full justify-start">
        {TABS.map((item) => (
          <TabsTrigger key={item.id} value={item.id}>
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="news" className="outline-none">
        <StockNewsSection
          code={code}
          reloadKey={reloadKey}
          showHeading={false}
        />
      </TabsContent>
      {(
        ["notices", "research", "block_trades", "holder_changes"] as const
      ).map((kind) => (
        <TabsContent key={kind} value={kind} className="outline-none">
          {tab === kind ? (
            <EventKindPanel code={code} kind={kind} reloadKey={reloadKey} />
          ) : null}
        </TabsContent>
      ))}
    </Tabs>
  )
}

function EventKindPanel({
  code,
  kind,
  reloadKey,
}: {
  code: string
  kind: StockEventKind
  reloadKey: number
}) {
  const [items, setItems] = useState<StockEventItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setItems([])
    void (async () => {
      try {
        const next = await queryStockEvents(code, kind)
        if (cancelled) {
          return
        }
        setItems(next.events ?? [])
        setError(next.error || null)
      } catch (err: unknown) {
        if (!cancelled) {
          setItems([])
          setError(err instanceof Error ? err.message : "暂时不可用")
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
  }, [code, kind, reloadKey])

  const empty = EMPTY_COPY[kind]
  const Icon = empty.icon

  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <Empty className="gap-2 border border-dashed p-4">
        <EmptyHeader className="gap-1">
          <EmptyMedia variant="icon">
            <Icon />
          </EmptyMedia>
          <EmptyTitle>{empty.title}</EmptyTitle>
          <EmptyDescription>{error || empty.description}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <ul className="flex flex-col">
      {items.map((item, index) => (
        <EventRow key={`${item.url || item.title}-${index}`} item={item} />
      ))}
    </ul>
  )
}

function EventRow({ item }: { item: StockEventItem }) {
  const meta = [item.source, item.published_at].filter(Boolean).join(" · ")
  const title = item.title || "未命名"
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
            <p className="min-w-0 flex-1 truncate text-sm font-medium">{title}</p>
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
