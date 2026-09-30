import { useEffect, useState } from 'react'
import type { Progress } from '../api'
import { L, stageText } from '../labels'

type Props = {
  progress: Progress
  stopping: boolean
  onStop: () => void
}

function fraction(p: Progress): number {
  if (p.stage === 'resample' && p.total) return (p.done ?? 0) / p.total
  if (!p.total) return 0
  const index = p.index ?? 0
  let within = 0
  if (p.stage === 'search' && p.max_holes && p.max_electrons && p.holes && p.electrons) {
    within = ((p.holes - 1) * p.max_electrons + p.electrons) / (p.max_holes * p.max_electrons + 1)
  } else if (p.stage === 'release' || p.stage === 'fixed') {
    within = 0.95
  }
  return Math.min(1, (index + within) / p.total)
}

export default function RunPanel({ progress, stopping, onStop }: Props) {
  const [started] = useState(() => Date.now())
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <section className="panel">
      <h2>{L.run_heading}</h2>
      <div className="bar"><div style={{ width: `${(fraction(progress) * 100).toFixed(1)}%` }} /></div>
      <div>{stageText(progress)}</div>
      <div className="note">{L.run_elapsed((now - started) / 1000)}</div>
      <div className="actions">
        <button className="danger" disabled={stopping} onClick={onStop}>{L.run_stop}</button>
        {stopping && <span className="note">{L.run_stopping}</span>}
      </div>
    </section>
  )
}
