/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useLocation } from "react-router"

import { JobDetailSheet } from "@/components/job-detail-sheet"
import { JobTracker } from "@/components/job-tracker"
import { listJobs, cancelJob as requestCancel, type Job } from "@/lib/api"
import { readDismissedJobs, writeDismissedJobs } from "@/lib/job-dismiss"
import {
  selectTrackerJobs,
  shouldPollJobs,
  SUCCESS_VISIBILITY_MS,
  TRACKER_JOB_LIMIT,
} from "@/lib/jobs"

type TrackOptions = {
  onSuccess?: (job: Job) => void | Promise<void>
  onFailure?: (job: Job) => void | Promise<void>
}

type JobContextValue = {
  jobs: Job[]
  loading: boolean
  error: string | null
  openJob: (jobId: string) => void
  dismissJob: (jobId: string) => void
  cancelJob: (jobId: string) => Promise<Job>
  trackJob: (job: Job, options?: TrackOptions) => void
  refreshJobs: () => Promise<Job[]>
}

const JobContext = createContext<JobContextValue | null>(null)

export function JobProvider({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openJobId, setOpenJobId] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState<Set<string>>(readDismissedJobs)
  const [clock, setClock] = useState(Date.now)
  const callbacksRef = useRef(new Map<string, TrackOptions>())

  const settleJob = useCallback((job: Job) => {
    if (job.status !== "succeeded" && job.status !== "failed") return
    const options = callbacksRef.current.get(job.id)
    if (!options) return
    callbacksRef.current.delete(job.id)
    const callback =
      job.status === "succeeded" ? options.onSuccess : options.onFailure
    if (callback) void Promise.resolve(callback(job))
  }, [])

  const mergeJob = useCallback(
    (job: Job) => {
      setJobs((current) => [
        job,
        ...current.filter((item) => item.id !== job.id),
      ])
      settleJob(job)
    },
    [settleJob]
  )

  const refreshJobs = useCallback(async () => {
    const next = await listJobs()
    setJobs(next)
    setError(null)
    for (const job of next) settleJob(job)
    return next
  }, [settleJob])

  useEffect(() => {
    let cancelled = false
    void refreshJobs()
      .catch((reason: unknown) => {
        if (!cancelled)
          setError(reason instanceof Error ? reason.message : "加载任务失败")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [refreshJobs])

  const forced = location.pathname === "/jobs"
  const polling = shouldPollJobs(jobs, dismissed, forced)
  useEffect(() => {
    if (!polling) return
    const timer = window.setInterval(() => {
      void refreshJobs().catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "刷新任务失败")
      })
    }, 2000)
    return () => window.clearInterval(timer)
  }, [polling, refreshJobs])

  useEffect(() => {
    const now = Date.now()
    const remaining = jobs
      .filter(
        (job) =>
          job.background &&
          job.status === "succeeded" &&
          job.finished_at &&
          !dismissed.has(job.id)
      )
      .map(
        (job) =>
          SUCCESS_VISIBILITY_MS - (now - new Date(job.finished_at!).getTime())
      )
      .filter((value) => value > 0)
    if (remaining.length === 0) return
    const timer = window.setTimeout(
      () => setClock(Date.now()),
      Math.min(...remaining) + 20
    )
    return () => window.clearTimeout(timer)
  }, [jobs, dismissed, clock])

  const trackerJobs = useMemo(
    () => selectTrackerJobs(jobs, dismissed, clock),
    [jobs, dismissed, clock]
  )
  const visibleTrackerJobs = trackerJobs.slice(0, TRACKER_JOB_LIMIT)

  const dismissJob = useCallback((jobId: string) => {
    setDismissed((current) => {
      const next = new Set(current)
      next.add(jobId)
      writeDismissedJobs(next)
      return next
    })
  }, [])

  const cancelTrackedJob = useCallback(
    async (jobId: string) => {
      const job = await requestCancel(jobId)
      mergeJob(job)
      return job
    },
    [mergeJob]
  )

  const trackJob = useCallback(
    (job: Job, options?: TrackOptions) => {
      if (options) callbacksRef.current.set(job.id, options)
      mergeJob(job)
    },
    [mergeJob]
  )

  const value = useMemo<JobContextValue>(
    () => ({
      jobs,
      loading,
      error,
      openJob: setOpenJobId,
      dismissJob,
      cancelJob: cancelTrackedJob,
      trackJob,
      refreshJobs,
    }),
    [jobs, loading, error, dismissJob, cancelTrackedJob, trackJob, refreshJobs]
  )

  return (
    <JobContext.Provider value={value}>
      {children}
      <JobTracker
        jobs={visibleTrackerJobs}
        allJobs={jobs}
        overflow={Math.max(0, trackerJobs.length - TRACKER_JOB_LIMIT)}
        onOpen={setOpenJobId}
        onDismiss={dismissJob}
        onCancel={(jobId) => {
          void cancelTrackedJob(jobId).catch((reason: unknown) => {
            setError(reason instanceof Error ? reason.message : "取消任务失败")
          })
        }}
      />
      <JobDetailSheet
        jobId={openJobId}
        onOpenChange={(open) => {
          if (!open) setOpenJobId(null)
        }}
        onDone={mergeJob}
      />
    </JobContext.Provider>
  )
}

export function useJobs() {
  const context = useContext(JobContext)
  if (!context) throw new Error("useJobs 需要放在 JobProvider 里")
  return context
}
