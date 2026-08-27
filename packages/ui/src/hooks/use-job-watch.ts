import { useEffect, useRef, useState } from "react"

import { getJob, watchJob, type Job } from "@/lib/api"
import { isOpenJob } from "@/lib/jobs"

export function useJobWatch(jobId: string | null, onDone?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    if (!jobId) {
      setJob(null)
      setLogs([])
      setError(null)
      setLoading(false)
      return
    }
    let cancelled = false
    let unwatch: (() => void) | undefined
    setJob(null)
    setLogs([])
    setError(null)
    setLoading(true)
    void getJob(jobId)
      .then((initial) => {
        if (cancelled) return
        const initialLogs = initial.log ?? []
        setJob(initial)
        setLogs(initialLogs)
        setLoading(false)
        if (!isOpenJob(initial.status)) return
        let skip = initialLogs.length
        unwatch = watchJob(
          initial.id,
          (line) => {
            if (skip > 0) {
              skip -= 1
              return
            }
            setLogs((current) => [...current, line])
          },
          (done) => {
            setJob(done)
            onDoneRef.current?.(done)
          },
          setError
        )
      })
      .catch((reason: unknown) => {
        if (cancelled) return
        setLoading(false)
        setError(reason instanceof Error ? reason.message : "读取任务失败")
      })
    return () => {
      cancelled = true
      unwatch?.()
    }
  }, [jobId])

  return { job, logs, error, loading }
}
