import { describe, expect, it } from "vitest"

import { reportSectionText } from "@/components/analyze/analyze-model"
import type { AnalyzeReportDetail } from "@/lib/api"

describe("analyze report sections", () => {
  it("collects nested research reports in a stable order", () => {
    const report = {
      code: "600000.SH",
      date: "2026-08-28",
      run_id: "run-1",
      sections: {
        bull: "看多",
        bear: "看空",
        manager: "结论",
      },
    } as AnalyzeReportDetail

    expect(reportSectionText(report, "research")).toBe("看多\n\n看空\n\n结论")
  })
})
