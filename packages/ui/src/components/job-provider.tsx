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
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { JobCancelDialog } from "@/components/job-cancel-dialog"
import { JobDetailSheet } from "@/components/job-detail-sheet"
import { JobTracker } from "@/components/job-tracker"
import {
  listJobs,
  cancelJob as requestCancel,
  watchJob,
  type Job,
} from "@/lib/api"
import { readDismissedJobs, writeDismissedJobs } from "@/lib/job-dismiss"
import { queryKeys } from "@/lib/query-keys"
import {
  isOpenJob,
  selectTrackerJobs,
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
  const queryClient = useQueryClient()
  const jobsQuery = useQuery({
    queryKey: queryKeys.jobs.list(),
    queryFn: () => listJobs(),
  })
  const jobs = jobsQuery.data ?? []
  const loading = jobsQuery.isLoading
  const [streamError, setStreamError] = useState<string | null>(null)
  const error =
    streamError ??
    (jobsQuery.error instanceof Error ? jobsQuery.error.message : null)
  const [openJobId, setOpenJobId] = useState<string | null>(null)
  const [pendingCancelId, setPendingCancelId] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState<Set<string>>(readDismissedJobs)
  const [clock, setClock] = useState(Date.now)
  const callbacksRef = useRef(new Map<string, TrackOptions>())
  const watchersRef = useRef(new Map<string, () => void>())

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
      queryClient.setQueryData<Job[]>(queryKeys.jobs.list(), (current = []) => [
        job,
        ...current.filter((item) => item.id !== job.id),
      ])
      settleJob(job)
    },
    [queryClient, settleJob]
  )

  const refreshJobs = useCallback(async () => {
    const result = await jobsQuery.refetch()
    if (result.error) throw result.error
    const next = result.data ?? []
    setStreamError(null)
    for (const job of next) settleJob(job)
    return next
  }, [jobsQuery, settleJob])

  useEffect(() => {
    const openIds = new Set(jobs.filter((job) => isOpenJob(job.status)).map((job) => job.id))
    for (const [jobId, close] of watchersRef.current) {
      if (!openIds.has(jobId)) {
        close()
        watchersRef.current.delete(jobId)
      }
    }
    for (const jobId of openIds) {
      if (watchersRef.current.has(jobId)) continue
      const close = watchJob(
        jobId,
        (line) => {
          queryClient.setQueryData<Job[]>(queryKeys.jobs.list(), (current = []) =>
            current.map((job) =>
              job.id === jobId
                ? {
                    ...job,
                    log: [...(job.log ?? []), line],
                    log_count: job.log_count + 1,
                  }
                : job
            )
          )
        },
        (done) => {
          watchersRef.current.delete(jobId)
          mergeJob(done)
        },
        (message) => {
          watchersRef.current.delete(jobId)
          setStreamError(message)
        }
      )
      watchersRef.current.set(jobId, close)
    }
  }, [jobs, mergeJob, queryClient])

  useEffect(
    () => () => {
      for (const close of watchersRef.current.values()) close()
      watchersRef.current.clear()
    },
    []
  )

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

  const requestCancelJob = useCallback((jobId: string) => {
    setCancelError(null)
    setPendingCancelId(jobId)
  }, [])

  const pendingCancelJob = useMemo(
    () => jobs.find((job) => job.id === pendingCancelId) ?? null,
    [jobs, pendingCancelId]
  )

  useEffect(() => {
    if (!pendingCancelJob) {
      return
    }
    if (!isOpenJob(pendingCancelJob.status)) {
      setPendingCancelId(null)
      setCancelling(false)
    }
  }, [pendingCancelJob])

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
        onCancel={requestCancelJob}
      />
      <JobDetailSheet
        jobId={openJobId}
        onOpenChange={(open) => {
          if (!open) setOpenJobId(null)
        }}
        onDone={mergeJob}
        onRequestCancel={requestCancelJob}
      />
      <JobCancelDialog
        job={pendingCancelId ? pendingCancelJob : null}
        busy={cancelling}
        error={cancelError}
        onOpenChange={(open) => {
          if (!open && !cancelling) {
            setPendingCancelId(null)
            setCancelError(null)
          }
        }}
        onConfirm={() => {
          if (!pendingCancelId) {
            return
          }
          setCancelling(true)
          setCancelError(null)
          void cancelTrackedJob(pendingCancelId)
            .then(() => {
              setPendingCancelId(null)
            })
            .catch((reason: unknown) => {
              setCancelError(
                reason instanceof Error ? reason.message : "取消任务失败"
              )
            })
            .finally(() => {
              setCancelling(false)
            })
        }}
      />
    </JobContext.Provider>
  )
}

export function useJobs() {
  const context = useContext(JobContext)
  if (!context) throw new Error("useJobs 需要放在 JobProvider 里")
  return context
}
