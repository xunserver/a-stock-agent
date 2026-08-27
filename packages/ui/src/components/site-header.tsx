import { Link, useLocation } from "react-router"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { navGroups } from "@/lib/nav"

function currentNav(pathname: string) {
  if (pathname === "/settings") {
    return { group: "管控面", page: "系统设置" }
  }
  for (const group of navGroups) {
    const item = group.items.find((entry) => entry.url === pathname)
    if (item) {
      return { group: group.title, page: item.title }
    }
  }
  return { group: "管控面", page: "概览" }
}

export function SiteHeader() {
  const { pathname } = useLocation()
  const { group, page } = currentNav(pathname)

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger />
      <Separator orientation="vertical" className="data-vertical:h-4" />
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink render={<Link to="/stocks" />}>{group}</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{page}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    </header>
  )
}
