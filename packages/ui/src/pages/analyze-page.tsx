import { InfoIcon } from "lucide-react"

import { AnalyzeReportBrowser } from "@/components/analyze/analyze-report-browser"
import { AnalyzeRunCard } from "@/components/analyze/analyze-run-card"
import { AnalyzeSetupCard } from "@/components/analyze/analyze-setup-card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { useAnalyzePageController } from "@/hooks/use-analyze-page-controller"

export function AnalyzePage() {
  const state = useAnalyzePageController()

  return (
    <div className="flex flex-col gap-4">
      <Alert>
        <InfoIcon />
        <AlertTitle>行情来源</AlertTitle>
        <AlertDescription>
          第 1 期行情来自 Yahoo，不是本地 market.db；A
          股覆盖一般，价格可能和股票池里的日线不一致。
        </AlertDescription>
      </Alert>
      <AnalyzeSetupCard
        loading={state.loading}
        poolItems={state.poolItems}
        memberItems={state.memberItems}
        poolId={state.poolId}
        code={state.code}
        date={state.date}
        analysts={state.analysts}
        selectedMember={state.selectedMember}
        needsKey={state.needsKey}
        needsBackend={state.needsBackend}
        needsModels={state.needsModels}
        hasRunning={state.hasRunning}
        canSubmit={state.canSubmit}
        submitting={state.submitting}
        onSelectPool={(value) => void state.onSelectPool(value)}
        onSelectCode={(value) => void state.onSelectCode(value)}
        onDateChange={state.setDate}
        onAnalystsChange={state.setAnalysts}
        onSubmit={() => void state.onSubmit()}
      />
      <AnalyzeRunCard
        job={state.job}
        jobs={state.jobs}
        logs={state.logs}
        decision={state.decision}
        logEndRef={state.logEndRef}
        onOpenReport={state.onOpenJobReport}
      />
      <div ref={state.reportCardRef}>
        <AnalyzeReportBrowser
          reports={state.reports}
          reportsLoading={state.reportsLoading}
          filterByCode={state.filterByCode}
          reportLoading={state.reportLoading}
          opened={state.opened}
          section={state.section}
          openedText={state.openedText}
          canSubmit={state.canSubmit}
          onToggleFilter={(checked) => void state.onToggleFilter(checked)}
          onOpenReport={(code, date, runId) =>
            void state.loadReport(code, date, runId)
          }
          onSectionChange={state.setSection}
          onSubmit={() => void state.onSubmit()}
        />
      </div>
      <p className="text-sm text-muted-foreground">研究工具，不是投资建议。</p>
    </div>
  )
}
