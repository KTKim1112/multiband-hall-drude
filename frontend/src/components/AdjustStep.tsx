// FR-112. Where a reader adjusts the answer after the fact, and confirms it.
//
// Step 5 is what the procedure found and is left alone. Here the reader pins a
// carrier count where the procedure landed somewhere unphysical, couples a
// band that cannot be read as one series, and -- when satisfied -- confirms.
//
// Confirming does not gather the rows on this screen. It sends the settings
// those adjustments amount to and the procedure runs again under them, which
// is why the files that come back are the files the command line writes for
// the document that comes back with them (FR-104, NR-013).

import { useState } from 'react'
import {
  ApiFailure, reportUrl, startConfirm, stopJob, tablesUrl,
  type AnalysisResult, type BandResult, type Coupling,
} from '../api'
import { fixed } from '../format'
import { L, errorText, stageText } from '../labels'
import { usePoll } from '../usePoll'
import {
  asBand, asSettings, isEmpty, without, withCoupling, withRefit,
  type Working,
} from '../working'
import { Carriers, Curves, Recount, Trends } from './Results'

type Props = {
  analysisId: string
  result: AnalysisResult
  working: Working
  onChange: (working: Working) => void
  onBack: () => void
}

export default function AdjustStep({
  analysisId, result, working, onChange, onBack,
}: Props) {
  const temps = result.temperatures
  const [selected, setSelected] = useState<number>(temps[0]?.T ?? 0)
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const { job, failure } = usePoll<AnalysisResult>(confirmId)

  const current = temps.find((t) => t.T === selected) ?? temps[0]
  const band = asBand(working, result.mode)

  async function confirm() {
    setError(null)
    setStopping(false)
    try {
      const settings = asSettings(working)
      setConfirmId((await startConfirm(
        analysisId, settings.fixed_counts, settings.smooth_band)).job_id)
    } catch (e) {
      const f = e instanceof ApiFailure ? e : new ApiFailure({ code: 'E_INTERNAL', params: {} })
      setError(errorText(f.code, f.params))
    }
  }

  const confirming = job !== null && (job.state === 'running' || job.state === 'pending')
  const confirmed = job?.state === 'succeeded' ? confirmId : null
  const shownError = error
    ?? (failure ? errorText(failure.code, failure.params) : null)
    ?? (job?.state === 'failed' && job.error ? errorText(job.error.code, job.error.params) : null)

  const settings = asSettings(working)
  const procedure = new Map(temps.map((t) => [t.T, t]))

  return (
    <section className="panel">
      <h2>{L.adjust_heading}</h2>
      <p className="lede">{L.adjust_lede}</p>
      <div className="actions">
        <button onClick={onBack}>{L.adjust_back}</button>
      </div>

      <h3>{L.adjust_pick}</h3>
      <div className="temps">
        {temps.map((t) => (
          <button key={t.T} className={t.T === current?.T ? 'chosen' : ''}
            onClick={() => setSelected(t.T)}>{t.T} K</button>
        ))}
      </div>

      {current && (
        <Recount analysisId={analysisId} temps={temps} t={current}
          onRefit={(refit: BandResult, holes: number, electrons: number) =>
            onChange(withRefit(working, refit, holes, electrons))}
          onCoupled={(coupling: Coupling) =>
            onChange(withCoupling(working, coupling))} />
      )}

      <h3>{L.adjust_working}</h3>
      {isEmpty(working)
        ? <p className="note">{L.adjust_nothing}</p>
        : (
          <div className="scroll">
            <table>
              <thead>
                <tr><th className="num">{L.col_T}</th><th>{L.trend_procedure}</th>
                  <th>{L.adjust_now}</th><th className="num">{L.recount_col_price}</th>
                  <th>{L.adjust_source}</th><th /></tr>
              </thead>
              <tbody>
                {Object.entries(working.byT)
                  .sort((a, b) => Number(a[0]) - Number(b[0]))
                  .map(([T, one]) => {
                    const was = procedure.get(Number(T))
                    const price = was?.rmsexx && one.row.rmsexx
                      ? one.row.rmsexx / was.rmsexx : null
                    return (
                      <tr key={T}>
                        <td className="num">{T}</td>
                        <td className="dim">{was ? was.label : ''}</td>
                        <td>{one.row.label}</td>
                        <td className={'num' + (price !== null && price > 1.01 ? ' bad' : '')}>
                          {price === null ? '' : fixed(price, 2) + 'x'}
                        </td>
                        <td>{one.row === one.pinned ? L.trend_refit : L.trend_coupled}</td>
                        <td>
                          <button onClick={() => onChange(without(working, Number(T)))}>
                            {L.adjust_undo}
                          </button>
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
        )}

      {band && current && (
        <>
          <h3>{L.curves_heading} — {current.T} K</h3>
          <Curves t={current} refit={band} split />
          <h3>{L.params_heading} — {current.T} K</h3>
          <Carriers t={current} refit={band} />
          <h3>{L.trends_heading}</h3>
          <p className="note">{L.trends_intro}</p>
          <Trends temps={temps} refit={band} split />
        </>
      )}

      <h3>{L.confirm_heading}</h3>
      <p className="note">{L.confirm_intro}</p>
      <p className="note">{L.confirm_settings(
        Object.keys(settings.fixed_counts).length, settings.smooth_band.length)}</p>
      <div className="actions">
        <button className="primary" disabled={confirming || isEmpty(working)}
          onClick={() => void confirm()}>
          {confirming ? L.confirm_running : L.confirm_run}
        </button>
        {confirming && (
          <button className="danger" disabled={stopping}
            onClick={() => { setStopping(true); void stopJob(confirmId!) }}>{L.run_stop}</button>
        )}
      </div>
      {confirming && job && (
        <>
          <div className="bar"><div style={{
            width: (((job.progress.index ?? 0) / (job.progress.total || 1)) * 100) + '%',
          }} /></div>
          <div className="note">{stageText(job.progress)}</div>
        </>
      )}
      {job?.state === 'stopped' && <div className="alert info">{L.confirm_stopped}</div>}
      {shownError && <div className="alert error">{shownError}</div>}
      {confirmed && (
        <>
          <div className="alert info">{L.confirm_done}</div>
          <div className="actions">
            <a href={reportUrl(confirmed)} download>
              <button>{L.results_download_page}</button>
            </a>
            <a href={tablesUrl(confirmed)} download>
              <button>{L.confirm_download_tables}</button>
            </a>
          </div>
        </>
      )}
    </section>
  )
}
