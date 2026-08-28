import { Link, useLocation } from "react-router"

import { MarketCalendarButton } from "@/components/market-calendar-button"
import { HeaderClock } from "@/components/header-clock"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { navGroups } from "@/lib/nav"

function currentNav(pathname: string) {
  if (pathname === "/settings") {
    return { group: "My Trading", page: "系统设置" }
  }
  if (pathname.startsWith("/automations/")) {
    return { group: "运行", page: "自动任务详情" }
  }
  for (const group of navGroups) {
    const item = group.items.find((entry) => entry.url === pathname)
    if (item) {
      return { group: group.title, page: item.title }
    }
  }
  return { group: "My Trading", page: "概览" }
}

export function SiteHeader() {
  const { pathname } = useLocation()
  const { group, page } = currentNav(pathname)

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b bg-background px-4">
      <SidebarTrigger />
      <Breadcrumb className="min-w-0 flex-1">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink render={<Link to="/stocks" />}>
              {group}
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{page}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="ml-auto flex shrink-0 items-center gap-2">
        <HeaderClock />
        <MarketCalendarButton />
      </div>
    </header>
  )
}
