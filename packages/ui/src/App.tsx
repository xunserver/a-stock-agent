import { Navigate, Outlet, Route, Routes } from "react-router"
import { SparklesIcon } from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import { SiteHeader } from "@/components/site-header"
import { ThemeProvider } from "@/components/theme-provider"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AnalyzePage } from "@/pages/analyze-page"
import { JobsPage } from "@/pages/jobs-page"
import { PlaceholderPage } from "@/pages/placeholder-page"
import { PoolPage } from "@/pages/pool-page"
import { SettingsPage } from "@/pages/settings-page"
import { StocksPage } from "@/pages/stocks-page"

function Shell() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <SiteHeader />
        <div className="flex flex-1 flex-col gap-4 p-4">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

export function App() {
  return (
    <ThemeProvider>
      <TooltipProvider>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<Navigate to="/stocks" replace />} />
            <Route path="/pools" element={<PoolPage />} />
            <Route path="/stocks" element={<StocksPage />} />
            <Route path="/analyze" element={<AnalyzePage />} />
            <Route
              path="/qlib"
              element={
                <PlaceholderPage
                  title="Qlib 候选"
                  description="从预测里取出的候选列表会放在这里。core 还没有接 qlib 命令。"
                  icon={SparklesIcon}
                />
              }
            />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </TooltipProvider>
    </ThemeProvider>
  )
}
