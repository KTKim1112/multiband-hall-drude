import { useEffect, useRef, useState } from 'react'
import { ApiFailure, getJob, type Job } from './api'

const FINAL = new Set(['succeeded', 'failed', 'stopped'])

// Polls one job once a second until it reaches a final state.
export function usePoll<R>(jobId: string | null): { job: Job<R> | null; failure: ApiFailure | null } {
  const [job, setJob] = useState<Job<R> | null>(null)
  const [failure, setFailure] = useState<ApiFailure | null>(null)
  const current = useRef(jobId)

  useEffect(() => {
    current.current = jobId
    setJob(null)
    setFailure(null)
    if (!jobId) return
    let timer: number | undefined
    let alive = true

    const tick = async () => {
      try {
        const view = await getJob<R>(jobId)
        if (!alive || current.current !== jobId) return
        setJob(view)
        if (!FINAL.has(view.state)) timer = window.setTimeout(tick, 1000)
      } catch (e) {
        if (!alive) return
        setFailure(e instanceof ApiFailure ? e : new ApiFailure({ code: 'E_INTERNAL', params: {} }))
      }
    }
    void tick()
    return () => {
      alive = false
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [jobId])

  return { job, failure }
}
