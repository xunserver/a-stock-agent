import { lazy, Suspense } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import { Navigate, Outlet, Route, Routes } from "react-router"

import { AppSidebar } from "@/components/app-sidebar"
import { AppToaster } from "@/components/app-toaster"
import { JobProvider } from "@/components/job-provider"
import { SiteHeader } from "@/components/site-header"
import { ThemeProvider } from "@/components/theme-provider"
import {
  StockDetailDialogHost,
  StockDetailProvider,
} from "@/components/stock-detail-provider"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { Spinner } from "@/components/ui/spinner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { queryClient } from "@/lib/query-client"

const AnalyzePage = lazy(() =>
  import("@/pages/analyze-page").then((module) => ({
    default: module.AnalyzePage,
  }))
)
const AutomationsPage = lazy(() =>
  import("@/pages/automations-page").then((module) => ({
    default: module.AutomationsPage,
  }))
)
const AutomationDetailPage = lazy(() =>
  import("@/pages/automations-page").then((module) => ({
    default: module.AutomationDetailPage,
  }))
)
const JobsPage = lazy(() =>
  import("@/pages/jobs-page").then((module) => ({ default: module.JobsPage }))
)
const PoolPage = lazy(() =>
  import("@/pages/pool-page").then((module) => ({ default: module.PoolPage }))
)
const QlibPage = lazy(() =>
  import("@/pages/qlib-page").then((module) => ({ default: module.QlibPage }))
)
const SettingsPage = lazy(() =>
  import("@/pages/settings-page").then((module) => ({
    default: module.SettingsPage,
  }))
)
const StocksPage = lazy(() =>
  import("@/pages/stocks-page").then((module) => ({
    default: module.StocksPage,
  }))
)

function Shell() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <SiteHeader />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="flex flex-col gap-4 p-4">
            <Outlet />
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider>
          <AppToaster />
          <StockDetailProvider>
            <JobProvider>
              <Suspense fallback={<PageFallback />}>
                <Routes>
                  <Route element={<Shell />}>
                    <Route
                      path="/"
                      element={<Navigate to="/stocks" replace />}
                    />
                    <Route path="/pools" element={<PoolPage />} />
                    <Route path="/stocks" element={<StocksPage />} />
                    <Route path="/analyze" element={<AnalyzePage />} />
                    <Route path="/qlib" element={<QlibPage />} />
                    <Route path="/automations" element={<AutomationsPage />} />
                    <Route
                      path="/automations/:automationId"
                      element={<AutomationDetailPage />}
                    />
                    <Route path="/jobs" element={<JobsPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                  </Route>
                </Routes>
              </Suspense>
              <StockDetailDialogHost />
            </JobProvider>
          </StockDetailProvider>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

function PageFallback() {
  return (
    <div className="flex min-h-48 items-center justify-center">
      <Spinner className="size-6" />
    </div>
  )
}
