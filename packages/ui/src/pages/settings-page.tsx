import { useEffect, useMemo, useState } from "react"
import { CircleAlertIcon, InfoIcon } from "lucide-react"

import { ModuleSections } from "@/components/settings/section-card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { querySettingsCatalog, type SettingsCatalog } from "@/lib/api"

export function SettingsPage() {
  const [catalog, setCatalog] = useState<SettingsCatalog | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const defaultModule = catalog?.modules[0]?.id ?? "ingest"
  const modules = useMemo(
    () =>
      (catalog?.modules ?? []).map((module) =>
        module.id === "ingest"
          ? {
              ...module,
              sections: module.sections.filter(
                (section) => section.id !== "schedule"
              ),
            }
          : module
      ),
    [catalog]
  )

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const next = await querySettingsCatalog()
        if (!cancelled) {
          setCatalog(next)
          setError(null)
        }
      } catch (err: unknown) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "加载失败")
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="flex flex-col gap-4">
      <Alert>
        <InfoIcon />
        <AlertTitle>设置存在系统库</AlertTitle>
        <AlertDescription>
          schema 和取值都写在 data/system.db，和行情库 market.db
          分开。按模块打开，每个小类单独保存。
        </AlertDescription>
      </Alert>
      {error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>无法读写系统设置</AlertTitle>
          <AlertDescription>{error}。确认 core 已启动。</AlertDescription>
        </Alert>
      ) : null}
      {loading && catalog === null ? (
        <Card>
          <CardHeader>
            <CardTitle>系统设置</CardTitle>
            <CardDescription>正在从系统库读取模块和 schema。</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </CardContent>
        </Card>
      ) : null}
      {catalog ? (
        <Tabs
          defaultValue={defaultModule}
          orientation="vertical"
          className="items-start"
        >
          <TabsList variant="line" className="w-44">
            {modules.map((module) => (
              <TabsTrigger key={module.id} value={module.id}>
                {module.title}
              </TabsTrigger>
            ))}
          </TabsList>
          {modules.map((module) => (
            <TabsContent
              key={module.id}
              value={module.id}
              className="w-full min-w-0"
            >
              <div className="flex flex-col gap-4">
                <div>
                  <h2 className="text-base font-medium">{module.title}</h2>
                  <p className="text-sm text-muted-foreground">
                    {module.description}
                  </p>
                </div>
                <ModuleSections
                  module={module}
                  onSectionSaved={(sectionId, next) =>
                    setCatalog((current) =>
                      !current
                        ? current
                        : {
                            ...current,
                            modules: current.modules.map((item) =>
                              item.id === module.id
                                ? {
                                    ...item,
                                    sections: item.sections.map((section) =>
                                      section.id === sectionId ? next : section
                                    ),
                                  }
                                : item
                            ),
                          }
                    )
                  }
                />
              </div>
            </TabsContent>
          ))}
        </Tabs>
      ) : null}
    </div>
  )
}
