import { useEffect, useState } from 'react'
import { health } from './api'

// AC-035. Short enough that the page is back before the reader has finished
// reading why it left, long enough to be nothing on a loopback address.
const EVERY_MS = 2000

/** Whether the program behind this page is there. FR-108.
 *
 * Asked on its own schedule rather than only when a step fails, so a window
 * left open from a previous run says what it is on sight, and so the page
 * comes back by itself when the program is started again. Nothing here
 * touches the reader's work: it is the page's own state.
 */
export function useServer(): { answering: boolean; checking: boolean; check: () => void } {
  const [answering, setAnswering] = useState(true)
  const [checking, setChecking] = useState(false)
  const [asked, setAsked] = useState(0)

  useEffect(() => {
    let alive = true
    let timer: number | undefined

    const tick = async () => {
      setChecking(true)
      let there = false
      try {
        await health()
        there = true
      } catch {
        there = false
      }
      if (!alive) return
      setAnswering(there)
      setChecking(false)
      timer = window.setTimeout(tick, EVERY_MS)
    }

    void tick()
    return () => {
      alive = false
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [asked])

  return { answering, checking, check: () => setAsked((n) => n + 1) }
}
