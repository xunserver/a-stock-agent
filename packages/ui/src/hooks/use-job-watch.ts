import { useEffect, useMemo, useRef, useState } from "react"

import { useJobs } from "@/components/job-provider"
import { getJob, type Job } from "@/lib/api"
import { isOpenJob } from "@/lib/jobs"

/** Read job details while JobProvider remains the only live SSE subscriber. */
export function useJobWatch(jobId: string | null, onDone?: (job: Job) => void) {
  const { jobs } = useJobs()
  const [initial, setInitial] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const onDoneRef = useRef(onDone)
  const notifiedRef = useRef<string | null>(null)
  onDoneRef.current = onDone

  useEffect(() => {
    if (!jobId) {
      setInitial(null)
      setError(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    void getJob(jobId)
      .then((job) => {
        if (!cancelled) setInitial(job)
      })
      .catch((reason: unknown) => {
        if (!cancelled)
          setError(reason instanceof Error ? reason.message : "读取任务失败")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [jobId])

  const live = useMemo(
    () => jobs.find((job) => job.id === jobId) ?? null,
    [jobs, jobId]
  )
  const job = live ?? initial

  useEffect(() => {
    if (!job || isOpenJob(job.status) || notifiedRef.current === job.id) return
    notifiedRef.current = job.id
    onDoneRef.current?.(job)
  }, [job])

  return { job, logs: job?.log ?? initial?.log ?? [], error, loading }
}
