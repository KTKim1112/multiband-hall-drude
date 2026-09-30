import { useEffect, useState } from 'react'
import {
  ApiFailure, reportUrl, startPrecise, startRecount, startSmooth, stopJob,
  tablesUrl,
  type AnalysisResult, type BandResult, type Coupling, type PreciseResult,
  type PreliminaryCarrier,
  type SpectrumBranch, type TemperatureResult,
} from '../api'
import { fixed, general, percent, sci } from '../format'
import { L, errorText, stageText } from '../labels'
import { usePoll } from '../usePoll'
import LinePlot, { type Series } from './LinePlot'

const HOLE = 'var(--hole)'
const ELECTRON = 'var(--electron)'
const MODEL = 'var(--model)'
const REFIT = 'var(--refit)'
const COUPLED = 'var(--coupled)'

// FR-109. A refit is shown beside the answer the procedure reached, never in
// place of it: the reader who overrode the count has to be able to see what
// the override did, and a plot that quietly swapped one for the other would
// hide exactly that. `null` where the band does not cover a temperature.
function rowAt(band: BandResult | null, T: number): TemperatureResult | null {
  return band?.temperatures.find((x) => x.T === T) ?? null
}

function coupledRowAt(band: BandResult | null, T: number): TemperatureResult | null {
  return band?.smoothing?.temperatures.find((x) => x.T === T) ?? null
}

function Badge({ grade }: { grade: string }) {
  return <span className={`badge ${grade === '-' ? 'dash' : grade}`} title={L.grade[grade] ?? grade}>{grade}</span>
}

function Verdicts({ temps, selected, onSelect }: {
  temps: TemperatureResult[]; selected: number; onSelect: (T: number) => void
}) {
  const peaks = temps.some((t) => t.mode === 'peaks')
  return (
    <>
      <h3>{L.verdict_heading}</h3>
      <p className="note">{L.verdict_intro}</p>
      {/* FR-090. Shown only where there is an island to explain. */}
      {temps.some((t) => t.island) && <p className="note">{L.island_intro}</p>}
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th className="num">{L.col_T}</th><th>{L.col_combo}</th>
              <th className="num">{L.col_fit_ratio}</th><th>{L.col_grade}</th>
              <th className="num">{L.col_r2xx}</th><th className="num">{L.col_r2xy}</th>
              <th className="num">{L.col_cond}</th><th>{L.col_failed}</th><th>{L.col_escaped}</th>
              <th>{L.col_undetermined}</th><th>{L.col_island}</th>
              {peaks && <th>{L.col_stop}</th>}
            </tr>
          </thead>
          <tbody>
            {temps.map((t) => (
              <tr key={t.T} className={`clickable${t.T === selected ? ' selected' : ''}`} onClick={() => onSelect(t.T)}>
                <td className="num">{t.T}</td>
                <td className={t.beyond ? 'bad' : ''}>{t.label}{t.beyond ? ` ${L.beyond_mark}` : ''}</td>
                <td className="num">{t.ratio_xx === null ? '—' : `${fixed(t.ratio_xx, 1)} / ${fixed(t.ratio_xy, 1)}`}</td>
                <td><Badge grade={t.grade} /> <span className="note">{L.grade[t.grade]}</span></td>
                <td className="num">{fixed(t.r2xx, 4)}</td>
                <td className="num">{fixed(t.r2xy, 4)}</td>
                <td className="num">{sci(t.condition, 2)}</td>
                <td className={t.failed.length ? 'bad' : 'dim'}>
                  {!t.carriers.length ? L.no_answer : t.failed.length ? t.failed.map((g) => L.gate[g] ?? g).join(', ') : L.none}
                </td>
                <td className={t.escaped.length ? 'bad' : 'dim'}>{t.escaped.length ? t.escaped.join(', ') : L.none}</td>
                <td className={t.undetermined ? 'bad' : 'dim'}>
                  {t.undetermined ? L.undetermined(t.undetermined, fixed(t.undetermined_ratio, 2)) : L.none}
                </td>
                <td className={t.island ? 'bad' : 'dim'}>
                  {t.island ? L.island_cell(t.island, fixed(t.island_price, 2)) : L.none}
                </td>
                {peaks && <td className={t.stop && t.stop !== 'converged' ? 'bad' : 'dim'}>{t.stop ? `${L.stop[t.stop] ?? t.stop} (${t.iterations})` : ''}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

export function Curves({ t, refit, split = false }: {
  t: TemperatureResult; refit: BandResult | null; split?: boolean
}) {
  if (!t.curve) return <p className="note">{L.no_curve}</p>
  const c = t.curve
  const again = rowAt(refit, t.T)
  const eased = coupledRowAt(refit, t.T)
  const pair = (
    y: (number | null)[], f: (number | null)[],
    fAgain: (number | null)[] | undefined, fEased: (number | null)[] | undefined,
  ): Series[] => {
    const out: Series[] = [
      { x: c.B, y, color: 'var(--dim)', label: L.measured, style: 'points' },
      { x: c.B, y: f, color: MODEL, label: L.model, style: 'line' },
    ]
    if (again?.curve && fAgain) {
      out.push({ x: again.curve.B, y: fAgain, color: REFIT, label: L.trend_refit, style: 'line' })
    }
    if (eased?.curve && fEased) {
      out.push({ x: eased.curve.B, y: fEased, color: COUPLED, label: L.trend_coupled, style: 'line' })
    }
    return out
  }

  // Two curves through the same points differ by less than the ink that draws
  // them, so overlaying the adjusted fit on the procedure's hides exactly what
  // the reader came to see. Split, each panel is one model against the
  // measurement, on one pair of axes. A sweep nobody adjusted has one answer
  // and keeps one plot.
  const standing = eased ?? again
  if (split && standing?.curve) {
    const shown = standing === eased ? L.trend_coupled : L.trend_refit
    const panels = (
      y: (number | null)[], f: (number | null)[], fNow: (number | null)[] | undefined,
      title: string, yLabel: string,
    ) => {
      const measured: Series = {
        x: c.B, y, color: 'var(--dim)', label: L.measured, style: 'points',
      }
      const was: Series[] = [measured,
        { x: c.B, y: f, color: MODEL, label: L.model, style: 'line' }]
      const now: Series[] = [measured]
      if (fNow) {
        now.push({ x: standing.curve!.B, y: fNow, color: REFIT, label: shown, style: 'line' })
      }
      return [
        <LinePlot key={`${title}-was`} title={`${title} · ${L.trend_procedure}`}
          xLabel={L.field} yLabel={yLabel} series={was} alongside={now} />,
        <LinePlot key={`${title}-now`} title={`${title} · ${L.trend_adjusted}`}
          xLabel={L.field} yLabel={yLabel} series={now} alongside={was} />,
      ]
    }
    return (
      <div className="plots">
        {panels(c.xx, c.fxx, standing.curve.fxx, `${t.T} K · ρxx`, L.rhoxx)}
        {panels(c.xy, c.fxy, standing.curve.fxy, `${t.T} K · ρxy`, L.rhoxy)}
      </div>
    )
  }

  return (
    <div className="plots">
      <LinePlot title={`${t.T} K · ρxx`} xLabel={L.field} yLabel={L.rhoxx}
        series={pair(c.xx, c.fxx, again?.curve?.fxx, eased?.curve?.fxx)} />
      <LinePlot title={`${t.T} K · ρxy`} xLabel={L.field} yLabel={L.rhoxy}
        series={pair(c.xy, c.fxy, again?.curve?.fxy, eased?.curve?.fxy)} />
    </div>
  )
}

export function Carriers({ t, refit }: { t: TemperatureResult; refit: BandResult | null }) {
  // FR-109. The values, not only the verdict. A reader who refits at their own
  // count wants the densities and mobilities it gave, beside the ones the
  // procedure chose, at the same temperature and in one table.
  const sets: { from: string; color: string; rows: TemperatureResult['carriers'] }[] = [
    { from: L.trend_procedure, color: MODEL, rows: t.carriers },
  ]
  const again = rowAt(refit, t.T)
  const eased = coupledRowAt(refit, t.T)
  if (again) sets.push({ from: L.trend_refit, color: REFIT, rows: again.carriers })
  if (eased) sets.push({ from: L.trend_coupled, color: COUPLED, rows: eased.carriers })
  const many = sets.length > 1
  return (
    <div className="scroll">
      <table>
        <thead>
          <tr>{many && <th>{L.col_source}</th>}
            <th>{L.col_name}</th><th>{L.col_kind}</th><th className="num">{L.col_density}</th>
            <th className="num">{L.col_mobility}</th><th className="num">{L.col_share}</th></tr>
        </thead>
        <tbody>
          {sets.flatMap((set) => set.rows.map((c) => (
            <tr key={`${set.from}-${c.name}`}>
              {many && <td style={{ color: set.color }}>{set.from}</td>}
              <td>{c.name}</td>
              <td style={{ color: c.kind === 'hole' ? HOLE : ELECTRON }}>{L[c.kind]}</td>
              <td className="num">{sci(c.n)}</td>
              <td className="num">{general(c.mu)}</td>
              <td className="num">{percent(c.share)}</td>
            </tr>
          )))}
        </tbody>
      </table>
    </div>
  )
}

export function Trends({ temps, refit, split = false }: {
  temps: TemperatureResult[]; refit: BandResult | null; split?: boolean
}) {
  // FR-090 exists because `n(T)` cannot be plotted across a model that changes
  // underneath it, which is the whole reason a reader pins a count. So the
  // pinned answer has to reach this plot; shown beside the procedure's, not
  // over it, and marked by shape so that colour keeps meaning carrier sign.
  const pick = (
    rows: TemperatureResult[], kind: 'hole' | 'electron', key: 'n' | 'mu',
    marker: 'circle' | 'square' | 'cross', from: string,
  ): Series => {
    const x: number[] = []
    const y: (number | null)[] = []
    for (const t of rows) for (const c of t.carriers) if (c.kind === kind) { x.push(t.T); y.push(c[key]) }
    return {
      x, y, marker, style: 'points',
      color: kind === 'hole' ? HOLE : ELECTRON,
      label: from ? `${L[kind]} · ${from}` : L[kind],
    }
  }
  const sets = (key: 'n' | 'mu'): Series[] => {
    const out: Series[] = []
    const add = (rows: TemperatureResult[], marker: 'circle' | 'square' | 'cross', from: string) => {
      for (const kind of ['hole', 'electron'] as const) {
        const series = pick(rows, kind, key, marker, from)
        if (series.x.length > 0) out.push(series)
      }
    }
    add(temps, 'circle', refit ? L.trend_procedure : '')
    if (refit) add(refit.temperatures, 'square', L.trend_refit)
    if (refit?.smoothing) add(refit.smoothing.temperatures, 'cross', L.trend_coupled)
    return out
  }

  // Side by side rather than on top of one another. Overlaid, a carrier that
  // moved and one that did not are two marks a few pixels apart among all the
  // others, and the reader cannot see which is which -- the one question the
  // adjustment step exists to answer. Split, each panel is a whole series and
  // the difference is the difference between two pictures. `alongside` keeps
  // them on one pair of axes, without which the comparison would be a lie.
  if (split && refit) {
    const coupled = new Set((refit.smoothing?.temperatures ?? []).map((t) => t.T))
    const adjusted = new Set(refit.temperatures.map((t) => t.T))
    const standing = (key: 'n' | 'mu'): Series[] => {
      const out: Series[] = []
      const add = (rows: TemperatureResult[], marker: 'circle' | 'square' | 'cross',
                   from: string) => {
        for (const kind of ['hole', 'electron'] as const) {
          const series = pick(rows, kind, key, marker, from)
          if (series.x.length > 0) out.push(series)
        }
      }
      // What the answer is now: coupled where a coupling ran, pinned where one
      // did not, and the procedure's own row at a sweep nobody touched -- so
      // the panel is a whole series and not the handful that were adjusted.
      add(temps.filter((t) => !adjusted.has(t.T)), 'circle', L.trend_procedure)
      add(refit.temperatures.filter((t) => !coupled.has(t.T)), 'square', L.trend_refit)
      if (refit.smoothing) add(refit.smoothing.temperatures, 'cross', L.trend_coupled)
      return out
    }
    const both = (key: 'n' | 'mu', label: string, title: string) => {
      const was = sets(key).filter((s) => s.marker === 'circle')
      const now = standing(key)
      return [
        <LinePlot key={`${key}-was`} title={`${title} · ${L.trend_procedure}`}
          xLabel={L.temperature} yLabel={label} logY series={was} alongside={now} />,
        <LinePlot key={`${key}-now`} title={`${title} · ${L.trend_adjusted}`}
          xLabel={L.temperature} yLabel={label} logY series={now} alongside={was} />,
      ]
    }
    return (
      <div className="plots">
        {both('n', L.density, L.density)}
        {both('mu', L.mobility, L.mobility)}
      </div>
    )
  }

  return (
    <div className="plots">
      <LinePlot title={L.density} xLabel={L.temperature} yLabel={L.density} logY series={sets('n')} />
      <LinePlot title={L.mobility} xLabel={L.temperature} yLabel={L.mobility} logY series={sets('mu')} />
    </div>
  )
}

function Candidates({ t }: { t: TemperatureResult }) {
  if (t.candidates.length === 0) return <p className="note">{L.cands_none}</p>
  return (
    <div className="scroll">
      <table>
        <thead>
          <tr><th className="num">{L.col_holes}</th><th className="num">{L.col_electrons}</th>
            <th className="num">{L.col_rmse}</th><th className="num">{L.col_cond}</th>
            <th className="num">{L.col_spread}</th><th className="num">{L.col_weakest}</th>
            <th>{L.col_bound}</th><th>{L.col_expired}</th>
            <th className="num">{L.col_starts}</th><th className="num">{L.col_seconds}</th></tr>
        </thead>
        <tbody>
          {t.candidates.map((c) => {
            const chosen = `${c.h}h+${c.e}e` === t.label
            return (
              <tr key={`${c.h}-${c.e}`} className={chosen ? 'selected' : ''}>
                <td className="num">{c.h}</td><td className="num">{c.e}</td>
                <td className="num">{sci(c.rmsexx)}</td><td className="num">{sci(c.condition, 2)}</td>
                <td className="num">{sci(c.spread, 2)}</td><td className="num">{percent(c.share, 2)}</td>
                <td className={c.bound ? 'bad' : 'dim'}>{c.bound ? L.yes : L.no}</td>
                {/* Constraint C18: running past the budget is a fact about the
                    machine, not a fault in the fit, so it is not marked bad.
                    What decides reproducibility is the spread, and how many
                    starting points it was measured across. */}
                <td className="dim">{c.expired ? L.yes : L.no}</td>
                <td className="num">{c.starts}</td>
                <td className="num">{c.seconds}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// FR-081. The picture the count and the window were read from. Folded away by
// default: the verdict comes first (FR-103), and this answers "why that count"
// for a reader who asks.
function peakSeries(branch: SpectrumBranch, color: string, label: string): Series {
  const weightAt = (mu: number) => {
    let best = 0
    let distance = Infinity
    branch.mobility_cm2Vs.forEach((grid, i) => {
      const apart = Math.abs(Math.log(grid) - Math.log(mu))
      if (apart < distance) { distance = apart; best = branch.weight[i] }
    })
    return best
  }
  return {
    x: branch.peaks_cm2Vs,
    y: branch.peaks_cm2Vs.map(weightAt),
    color, label, style: 'points',
  }
}

function Spectrum({ t }: { t: TemperatureResult }) {
  if (!t.spectrum) return <p className="note">{L.spectrum_none}</p>
  const { hole, electron } = t.spectrum
  const series: Series[] = [
    { x: hole.mobility_cm2Vs, y: hole.weight, color: HOLE, label: L.spectrum_hole, style: 'line' },
    { x: electron.mobility_cm2Vs, y: electron.weight, color: ELECTRON,
      label: L.spectrum_electron, style: 'line' },
    peakSeries(hole, HOLE, L.spectrum_peak_hole),
    peakSeries(electron, ELECTRON, L.spectrum_peak_electron),
  ]
  return (
    <>
      <p className="note">{L.spectrum_intro}</p>
      <LinePlot series={series} title={L.spectrum_title(t.T)}
        xLabel={L.spectrum_x} yLabel={L.spectrum_y} logX />
      {Object.entries(t.window).map(([kind, edges]) => (
        <p className="note" key={kind}>
          {L.spectrum_window(kind, general(edges[0]), general(edges[1]))}
        </p>
      ))}
    </>
  )
}

const COUNTED = /^(\d+)h\+(\d+)e$/

// FR-109. The procedure chose a count from the data; this asks what another
// one costs. The verdict it reached stays on screen beside the answer, and the
// price of the override is stated, so overriding is a decision and not a way
// to make the disagreement disappear.
const shorthand = (x: TemperatureResult | undefined) =>
  !x ? '' : `${x.label} · ${x.grade}${x.ratio_xx === null ? '' : ` · ${fixed(x.ratio_xx, 2)}`}`

export function Recount({ analysisId, temps, t, onRefit, onCoupled }: {
  analysisId: string; temps: TemperatureResult[]; t: TemperatureResult
  onRefit: (band: BandResult, holes: number, electrons: number) => void
  onCoupled: (coupling: Coupling) => void
}) {
  const [holes, setHoles] = useState(1)
  const [electrons, setElectrons] = useState(1)
  const [from, setFrom] = useState(t.T)
  const [to, setTo] = useState(t.T)
  const [strength, setStrength] = useState('normal')
  const [jobId, setJobId] = useState<string | null>(null)
  const [smoothId, setSmoothId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const { job, failure } = usePoll<BandResult>(jobId)
  const coupling = usePoll<Coupling>(smoothId)

  useEffect(() => {
    // The form follows whichever temperature is selected -- but only while
    // nothing has been refitted yet. A band refit is the case that matters
    // (FR-109), and a reader who refits 40-90 K and then clicks through those
    // temperatures to compare the curves must not have the comparison thrown
    // away by the clicking.
    if (jobId !== null) return
    const counted = COUNTED.exec(t.label)
    setHoles(counted ? Number(counted[1]) : 1)
    setElectrons(counted ? Number(counted[2]) : 1)
    setFrom(t.T)
    setTo(t.T)
    setError(null)
  }, [t.T, t.label, jobId])

  const low = Math.min(from, to)
  const high = Math.max(from, to)
  const band = temps.filter((x) => x.T >= low && x.T <= high)

  function failed(e: unknown) {
    const f = e instanceof ApiFailure ? e : new ApiFailure({ code: 'E_INTERNAL', params: {} })
    setError(errorText(f.code, f.params))
  }

  async function run() {
    setError(null)
    setStopping(false)
    setSmoothId(null)
    try {
      setJobId((await startRecount(
        analysisId, band.map((x) => x.T), holes, electrons)).job_id)
    } catch (e) { failed(e) }
  }

  // FR-109, amended. Asked of the refit, not alongside it: a coupling over a
  // long band takes far longer than the refits it follows, and while the two
  // were one request, asking for one hid the other.
  async function couple() {
    setError(null)
    setStopping(false)
    try {
      setSmoothId((await startSmooth(jobId!, strength)).job_id)
    } catch (e) { failed(e) }
  }

  const running = job !== null && (job.state === 'running' || job.state === 'pending')
  const refit = job?.state === 'succeeded' ? job.result : null
  const smoothing = coupling.job?.state === 'running' || coupling.job?.state === 'pending'
  const coupled = coupling.job?.state === 'succeeded' ? coupling.job.result : null

  const shownError = error
    ?? (failure ? errorText(failure.code, failure.params) : null)
    ?? (job?.state === 'failed' && job.error ? errorText(job.error.code, job.error.params) : null)
    ?? (coupling.failure ? errorText(coupling.failure.code, coupling.failure.params) : null)
    ?? (coupling.job?.state === 'failed' && coupling.job.error
      ? errorText(coupling.job.error.code, coupling.job.error.params) : null)

  const before = new Map(temps.map((x) => [x.T, x]))

  // Lifted out as each half arrives. They are reported separately because they
  // accumulate separately: a refit sets the count standing at its sweeps, a
  // coupling refines sweeps already pinned (FR-112).
  useEffect(() => {
    if (refit !== null) onRefit(refit, holes, electrons)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refit])

  useEffect(() => {
    if (coupled !== null) onCoupled(coupled)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coupled])

  const bar = ((job?.progress.index ?? 0) / (job?.progress.total || 1)) * 100

  return (
    <>
      <p className="note">{L.recount_intro}</p>
      <div className="actions">
        <label>{L.recount_holes}{' '}
          <input type="number" min={0} max={8} value={holes}
            onChange={(e) => setHoles(Math.max(0, Number(e.target.value)))} />
        </label>
        <label>{L.recount_electrons}{' '}
          <input type="number" min={0} max={8} value={electrons}
            onChange={(e) => setElectrons(Math.max(0, Number(e.target.value)))} />
        </label>
        <label>{L.recount_from}{' '}
          <select value={from} onChange={(e) => setFrom(Number(e.target.value))}>
            {temps.map((x) => <option key={x.T} value={x.T}>{x.T} K</option>)}
          </select>
        </label>
        <label>{L.recount_to}{' '}
          <select value={to} onChange={(e) => setTo(Number(e.target.value))}>
            {temps.map((x) => <option key={x.T} value={x.T}>{x.T} K</option>)}
          </select>
        </label>
        <button className="primary" disabled={running || smoothing || band.length === 0}
          onClick={() => void run()}>
          {running ? L.recount_running : L.recount_run}
        </button>
        {running && (
          <button className="danger" disabled={stopping}
            onClick={() => { setStopping(true); void stopJob(jobId!) }}>{L.run_stop}</button>
        )}
      </div>
      <p className="note">{L.recount_chosen(band.length)}</p>
      {running && job && (
        <>
          <div className="bar"><div style={{ width: bar + '%' }} /></div>
          <div className="note">{stageText(job.progress)}</div>
        </>
      )}
      {job?.state === 'stopped' && <div className="alert info">{L.recount_stopped}</div>}
      {shownError && <div className="alert error">{shownError}</div>}
      {/* FR-109. A pin the fit could not honour is named. Folding these sweeps
          into the answer would report the count the reader overrode as though
          it were the count they asked for. */}
      {refit && refit.unheld?.length > 0 && (
        <div className="alert warn">
          {L.recount_unheld(refit.unheld.map((T) => `${T} K`).join(', '))}
        </div>
      )}

      {refit && (
        <>
          <div className="alert info">{L.recount_shown}</div>
          <p className="note">
            {refit.roughness === null ? L.roughness_none
              : L.roughness_note(fixed(refit.roughness, 3))}
          </p>

          <p className="note">{L.smooth_intro}</p>
          <p className="note">{L.smooth_ask(refit.temperatures.length)}</p>
          {refit.temperatures.length < 3 && <p className="note">{L.smooth_needs}</p>}
          {refit.temperatures.length > 8 && (
            <div className="alert warn">{L.smooth_long_band(refit.temperatures.length)}</div>
          )}
          <div className="actions">
            <label>{L.smooth_label}{' '}
              <select value={strength} onChange={(e) => setStrength(e.target.value)}>
                <option value="weak">{L.smooth_weak}</option>
                <option value="normal">{L.smooth_normal}</option>
                <option value="strong">{L.smooth_strong}</option>
              </select>
            </label>
            <button disabled={smoothing || refit.temperatures.length < 3}
              onClick={() => void couple()}>
              {smoothing ? L.smooth_running : L.smooth_run}
            </button>
            {smoothing && (
              <button className="danger" disabled={stopping}
                onClick={() => { setStopping(true); void stopJob(smoothId!) }}>{L.run_stop}</button>
            )}
          </div>
          {smoothing && coupling.job && (
            // The band is one calculation, so elapsed against the budget is the
            // only honest denominator; there is nothing to count by.
            <div className="note">
              {L.smooth_elapsed(fixed(coupling.job.progress.seconds ?? 0, 0),
                                fixed(coupling.job.progress.budget ?? 0, 0))}
            </div>
          )}
          {coupling.job?.state === 'stopped' && (
            <div className="alert info">{L.smooth_stopped}</div>
          )}
          {coupled && (
            <p className="note">
              {L.smooth_done(
                L[('smooth_' + coupled.strength) as 'smooth_weak'],
                fixed(refit.roughness, 3),
                fixed(coupled.roughness, 3))}
            </p>
          )}

          <div className="scroll">
            <table>
              <thead>
                <tr><th className="num">{L.col_T}</th><th>{L.recount_original}</th>
                  <th>{L.recount_result}</th>
                  <th className="num">{L.recount_col_price}</th>
                  {coupled && <>
                    <th>{L.smooth_col}</th>
                    <th className="num">{L.recount_col_price}</th>
                  </>}
                </tr>
              </thead>
              <tbody>
                {refit.temperatures.map((row) => {
                  const was = before.get(row.T)
                  const price = was?.rmsexx && row.rmsexx ? row.rmsexx / was.rmsexx : null
                  const eased = coupled?.temperatures.find((x) => x.T === row.T)
                  const paid = eased?.rmsexx && row.rmsexx ? eased.rmsexx / row.rmsexx : null
                  return (
                    <tr key={row.T}>
                      <td className="num">{row.T}</td>
                      <td className="dim">{shorthand(was)}</td>
                      <td>{shorthand(row)}</td>
                      <td className={'num' + (price !== null && price > 1.01 ? ' bad' : '')}>
                        {price === null ? '' : fixed(price, 2) + 'x'}
                      </td>
                      {coupled && <>
                        <td>{shorthand(eased)}</td>
                        <td className={'num' + (paid !== null && paid > 1.01 ? ' bad' : '')}>
                          {paid === null ? '' : fixed(paid, 2) + 'x'}
                        </td>
                      </>}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}


function Precise({ analysisId, t }: { analysisId: string; t: TemperatureResult }) {
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const { job, failure } = usePoll<PreciseResult>(jobId)

  useEffect(() => { setJobId(null); setError(null); setStopping(false) }, [t.T])

  if (!t.carriers.length) return <p className="note">{L.no_answer}</p>

  async function start() {
    setError(null)
    setStopping(false)
    try {
      setJobId((await startPrecise(analysisId, t.T)).job_id)
    } catch (e) {
      const f = e instanceof ApiFailure ? e : new ApiFailure({ code: 'E_INTERNAL', params: {} })
      setError(errorText(f.code, f.params))
    }
  }

  const running = job !== null && (job.state === 'running' || job.state === 'pending')
  const result = job?.state === 'succeeded' ? job.result : null
  const shownError = error ?? (failure ? errorText(failure.code, failure.params) : null)
    ?? (job?.state === 'failed' && job.error ? errorText(job.error.code, job.error.params) : null)

  return (
    <>
      <p className="note">{L.precise_intro}</p>
      <div className="actions">
        <button className="primary" disabled={running || jobId !== null && !job} onClick={() => void start()}>
          {L.precise_start(t.T)}
        </button>
        {running && (
          <button className="danger" disabled={stopping}
            onClick={() => { setStopping(true); void stopJob(jobId!) }}>{L.run_stop}</button>
        )}
      </div>
      {running && job && (
        <>
          <div className="bar"><div style={{ width: `${((job.progress.done ?? 0) / (job.progress.total || 1)) * 100}%` }} /></div>
          <div className="note">{job.progress.stage === 'resample' ? L.precise_running(job.progress.done ?? 0, job.progress.total ?? 0) : stageText(job.progress)}</div>
        </>
      )}
      {job?.state === 'stopped' && <div className="alert info">{L.precise_stopped}</div>}
      {shownError && <div className="alert error">{shownError}</div>}
      {result && (
        <>
          <div className="note">{L.precise_result(result.resamples, result.block_length, result.seed)}</div>
          {result.lower_bound && <div className="alert warn">{L.precise_lower_bound}</div>}
          <div className="scroll">
            <table>
              <thead><tr><th>{L.col_quantity}</th><th className="num">{L.col_value}</th><th className="num">{L.col_low}</th>
                <th className="num">{L.col_high}</th><th className="num">{L.col_relative}</th></tr></thead>
              <tbody>
                {[...result.parameters, ...result.derived].map((row) => (
                  <tr key={row.quantity}>
                    <td>{row.quantity}</td><td className="num">{general(row.value)}</td>
                    <td className="num">{general(row.low)}</td><td className="num">{general(row.high)}</td>
                    <td className="num">{percent(row.relative_one_sigma)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}

type Props = {
  jobId: string
  state: 'succeeded' | 'stopped'
  result: AnalysisResult
  preliminary: PreliminaryCarrier[] | null
  onNew: () => void
  // FR-112. The working answer lives in the step that builds it, and is shown
  // here beside the procedure's own. `null` until something is adjusted.
  refit: BandResult | null
  onAdjust: () => void
}

export default function Results({
  jobId, state, result, preliminary, onNew, refit, onAdjust,
}: Props) {
  const temps = result.temperatures
  const [selected, setSelected] = useState<number>(temps[0]?.T ?? 0)
  const current = temps.find((t) => t.T === selected) ?? temps[0]
  const band = refit ? refit.temperatures.map((x) => x.T) : []

  return (
    <section className="panel">
      <h2>{L.results_heading}</h2>
      {state === 'stopped' && <div className="alert warn">{L.results_stopped}</div>}
      {/* FR-005. Rows the server could not place are dropped before the
          library is handed the table, so the library's own count cannot see
          them. Silence here can hide a whole sweep. */}
      {!!result.dropped_before_fit && (
        <div className="alert warn">{L.results_dropped(result.dropped_before_fit)}</div>
      )}
      <div className="alert info">{result.mode === 'peaks' ? L.count_notice_peaks_cli : L.count_notice_data}</div>
      <div className="note">
        {L.results_seconds(result.seconds)}
        {preliminary && <> · {L.results_prelim(preliminary.map((c) => `${c.name} (${general(c.mobility_cm2Vs)} cm²/Vs)`).join(', '))}</>}
      </div>
      <div className="actions">
        {state === 'succeeded' && (
          <>
            <a href={reportUrl(jobId)} download><button>{L.results_download_page}</button></a>
            <a href={tablesUrl(jobId)} download><button>{L.results_download_tables}</button></a>
          </>
        )}
        <button onClick={onNew}>{L.results_new}</button>
      </div>

      <Verdicts temps={temps} selected={current?.T ?? 0} onSelect={setSelected} />

      {current && (
        <>
          <div className="temps">
            {temps.map((t) => (
              <button key={t.T} className={t.T === current.T ? 'chosen' : ''} onClick={() => setSelected(t.T)}>{t.T} K</button>
            ))}
          </div>
          <details className="panel">
            <summary>{L.spectrum_show}</summary>
            <Spectrum t={current} />
          </details>
          {refit && (
            <div className="alert info">
              {L.refit_showing(
                rowAt(refit, current.T)?.label ?? refit.temperatures[0]?.label ?? '',
                band.length === 1 ? `${band[0]} K` : `${Math.min(...band)}–${Math.max(...band)} K`,
              )}
            </div>
          )}
          <h3>{L.curves_heading} — {current.T} K, {current.label}</h3>
          <Curves t={current} refit={refit} />
          <h3>{L.params_heading} — {current.T} K</h3>
          <Carriers t={current} refit={refit} />
          {state === 'succeeded' && (
            <>
              <h3>{L.precise_heading}</h3>
              <Precise analysisId={jobId} t={current} />
              <h3>{L.recount_heading}</h3>
              <p className="note">{L.adjust_moved}</p>
              <div className="actions">
                <button className="primary" onClick={onAdjust}>{L.adjust_go}</button>
              </div>
            </>
          )}
          <h3>{L.trends_heading}</h3>
          <p className="note">{L.trends_intro}</p>
          <Trends temps={temps} refit={refit} />
          <h3>{L.cands_heading} — {current.T} K</h3>
          <Candidates t={current} />
        </>
      )}

      <footer className="notice">
        <p>{L.notice_interval}</p>
        <p>{L.notice_mobility}</p>
        <p>{L.notice_peaks}</p>
      </footer>
    </section>
  )
}
