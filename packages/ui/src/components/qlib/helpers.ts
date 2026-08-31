import type { Job, QlibWorkflow } from "@/lib/api"

export const WORKFLOW_OPTIONS = [
  { value: "workflow_lightgbm_alpha158", label: "LightGBM + Alpha158" },
  { value: "workflow_lightgbm_focus5", label: "LightGBM + Focus5" },
]
export const TOP_DISPLAY_OPTIONS = [5, 10, 20, 50] as const

export function jobPool(job: Job): string {
  return typeof job.command.pool === "string" ? job.command.pool : ""
}
export function isQlibPoolJob(job: Job): boolean {
  return job.type === "qlib.run" || job.type === "qlib.dump"
}
export function formatScore(score: number): string {
  return Number.isFinite(score) ? score.toFixed(6) : "—"
}
export function copyWorkflow(workflow: QlibWorkflow): QlibWorkflow {
  return {
    config: workflow.config,
    benchmark: workflow.benchmark,
    topk: workflow.topk,
    n_drop: workflow.n_drop,
    account: workflow.account,
    data_end: workflow.data_end ?? null,
    test_start: workflow.test_start ?? null,
    learning_rate: workflow.learning_rate ?? null,
  }
}
export function topOptionsFor(count: number) {
  if (!count) return []
  const values = new Set<number>()
  for (const value of TOP_DISPLAY_OPTIONS) if (value <= count) values.add(value)
  values.add(count)
  return [...values]
    .sort((left, right) => left - right)
    .map((value) => ({ value: String(value), label: `Top ${value}` }))
}
