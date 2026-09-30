// FR-109, rendered and counted rather than reasoned about.
//
// The type checker cannot see that a refit reaches the plots: passing it down
// and never drawing it type-checks perfectly. So the components are rendered
// to static markup here and the marks are counted. Run by
// `npm run check:render`, and by `tests/test_frontend_render.py` where node is
// present.
import { renderToStaticMarkup } from 'react-dom/server'
import Results, { Carriers, Curves, Trends } from './components/Results'
import {
  EMPTY, asSettings, withCoupling as applyCoupling, withRefit as applyRefit,
  without as undoAt,
} from './working'
import type { AnalysisResult, BandResult, TemperatureResult } from './api'

const carrier = (name: string, kind: 'hole' | 'electron', n: number, mu: number) =>
  ({ name, kind, n, mu, share: 0.5 })

const curve = () => {
  const B = Array.from({ length: 21 }, (_, i) => -9 + i * 0.9)
  return { B, xx: B.map((b) => 1 + 0.01 * b * b), xy: B.map((b) => 0.05 * b),
           fxx: B.map((b) => 1 + 0.011 * b * b), fxy: B.map((b) => 0.051 * b) }
}

const temp = (T: number, label: string, holes: number, electrons: number): TemperatureResult => ({
  T, mode: 'data', label, grade: 'A', beyond: false,
  ratio_xx: 2.1, ratio_xy: 1.8, runs_xx: 0.4, r2xx: 0.999, r2xy: 0.999,
  rmsexx: 0.01, rmsexy: 0.002, condition: 300, spread: 1e-7,
  failed: [], escaped: [], undetermined: '', undetermined_ratio: null,
  island: '', island_price: null, spectrum: null, window: {},
  iterations: 3, stop: 'converged', seconds: 12,
  carriers: [
    ...Array.from({ length: holes }, (_, i) => carrier(`h${i + 1}`, 'hole', 1e20 * (i + 1), 9000 / (i + 1))),
    // The electron mobilities sit a decade below the hole ones so that the
    // logarithmic axis actually carries a tick. Without one the axis draws no
    // grid line, and the check below -- which reads the grid to see whether two
    // panels share a scale -- would have nothing to read.
    ...Array.from({ length: electrons }, (_, i) => carrier(`e${i + 1}`, 'electron', 2e20 * (i + 1), 700 / (i + 1))),
  ],
  candidates: [], curve: curve(),
} as unknown as TemperatureResult)

const base: AnalysisResult = {
  mode: 'data', seconds: 100,
  temperatures: [temp(5, '1h+1e', 1, 1), temp(10, '1h+1e', 1, 1), temp(20, '2h+1e', 2, 1)],
}

const band: BandResult = {
  mode: 'data', seconds: 40,
  temperatures: [temp(5, '2h+2e', 2, 2), temp(10, '2h+2e', 2, 2), temp(20, '2h+2e', 2, 2)],
  roughness: 0.431,
  smoothing: {
    strength: 'normal', lambda: 1e-4, roughness: 0.2,
    temperatures: [temp(5, '2h+2e', 2, 2), temp(10, '2h+2e', 2, 2), temp(20, '2h+2e', 2, 2)],
  },
  unheld: [],
}

function count(html: string, needle: string) {
  return html.split(needle).length - 1
}

const plain = renderToStaticMarkup(
  <Results jobId="j" state="succeeded" result={base} preliminary={null}
    onNew={() => {}} refit={null} onAdjust={() => {}} />)

// FR-112. The working answer reaches step 5 as well: a reader who adjusts and
// then walks back must see what they adjusted, beside what the procedure
// found. Threading it through every component and never drawing it type-checks
// perfectly, which is the whole reason this file exists.
const resultsWithWorking = renderToStaticMarkup(
  <Results jobId="j" state="succeeded" result={base} preliminary={null}
    onNew={() => {}} refit={band} onAdjust={() => {}} />)

// The overlay is held in Results' own state, which static rendering cannot
// set, so the components that take it are rendered directly as well.
const withRefit = renderToStaticMarkup(<Trends temps={base.temperatures} refit={band} />)
const withoutRefit = renderToStaticMarkup(<Trends temps={base.temperatures} refit={null} />)

const carriersPlain = renderToStaticMarkup(<Carriers t={base.temperatures[0]} refit={null} />)
const carriersBoth = renderToStaticMarkup(<Carriers t={base.temperatures[0]} refit={band} />)
const curvesBoth = renderToStaticMarkup(<Curves t={base.temperatures[0]} refit={band} />)

// The adjustment step draws the two answers as separate panels, because two
// curves through the same points differ by less than the ink that draws them.
// Separate panels are only a comparison if they share a pair of axes, and a
// panel that quietly rescaled itself would look right and read wrong -- so the
// grid lines of the two panels are compared, which is where the scale shows.
const trendsSplit = renderToStaticMarkup(
  <Trends temps={base.temperatures} refit={band} split />)
const curvesSplit = renderToStaticMarkup(
  <Curves t={base.temperatures[0]} refit={band} split />)

const panels = (html: string) => html.split('<svg').slice(1)
const gridLines = (panel: string) =>
  (panel.match(/class="grid"[^/]*?y1="([-0-9.]+)"/g) ?? []).join('|')
const sameAxes = (html: string, a: number, b: number) => {
  const all = panels(html)
  const one = gridLines(all[a] ?? '')
  return one !== '' && one === gridLines(all[b] ?? '') ? 1 : 0
}

// FR-112. The accumulation itself, which no type checker can see: adjustments
// that overwrite each other instead of accumulating type-check perfectly.
const twice = applyRefit(
  applyRefit(EMPTY, { ...band, temperatures: [temp(5, '2h+2e', 2, 2)] }, 2, 2),
  { ...band, temperatures: [temp(20, '1h+1e', 1, 1)] }, 1, 1)
const overwritten = applyRefit(
  twice, { ...band, temperatures: [temp(5, '1h+1e', 1, 1)] }, 1, 1)
const coupledBand = applyCoupling(
  applyRefit(EMPTY, band, 2, 2),
  { strength: 'normal', lambda: 1e-4, roughness: 0.2,
    temperatures: [temp(5, '2h+2e', 2, 2), temp(10, '2h+2e', 2, 2),
                   temp(20, '2h+2e', 2, 2)] })
const undone = undoAt(coupledBand, 10)
// FR-112. A refit inside a coupled band ends that band, exactly as undoing a
// sweep inside it does. A stale coupling left here reaches the confirm: where
// the refit changed the count the procedure refuses the band outright, and
// where it did not the sweep is coupled again although the page draws it as
// independently refitted.
const refittedInside = applyRefit(
  coupledBand, { ...band, temperatures: [temp(10, '1h+1e', 1, 1)] }, 1, 1)

const failures: string[] = []
function expect(what: string, got: number, want: number) {
  if (got !== want) failures.push(`${what}: ${got}, expected ${want}`)
}

const report = {
  plain_circles: count(plain, '<circle'),
  plain_squares: count(plain, '<rect'),
  trends_no_refit: {
    circles: count(withoutRefit, '<circle'), squares: count(withoutRefit, '<rect'),
    crosses: count(withoutRefit, 'stroke-width="1.4"'),
    legend: count(withoutRefit, '<text x="22"'),
  },
  trends_with_refit: {
    circles: count(withRefit, '<circle'), squares: count(withRefit, '<rect'),
    crosses: count(withRefit, 'stroke-width="1.4"'),
    legend: count(withRefit, '<text x="22"'),
  },
  carrier_rows_plain: count(carriersPlain, '<tr') - 1,
  carrier_rows_with_refit: count(carriersBoth, '<tr') - 1,
  carrier_columns_plain: count(carriersPlain, '</th>'),
  carrier_columns_with_refit: count(carriersBoth, '</th>'),
  curve_paths_with_refit: count(curvesBoth, '<path'),
  results_squares_plain: count(plain, '<rect'),
  results_squares_with_working: count(resultsWithWorking, '<rect'),
}
console.log(JSON.stringify(report, null, 2))

// Three temperatures carrying 1h+1e, 1h+1e and 2h+1e make 7 marks per plot,
// and two plots and two legend keys make 18. The refit and the coupling carry
// 2h+2e over the same three temperatures: 12 marks per plot, 24 over two, and
// six legend keys in all.
expect('procedure marks', report.trends_no_refit.circles, 18)
expect('nothing but the procedure before a refit',
       report.trends_no_refit.squares + report.trends_no_refit.crosses, 0)
expect('the procedure is not replaced', report.trends_with_refit.circles, 18)
expect('the refit is drawn', report.trends_with_refit.squares, 28)
expect('the coupling is drawn', report.trends_with_refit.crosses, 28)
expect('every set is named', report.trends_with_refit.legend, 12)
expect('carrier rows, procedure only', report.carrier_rows_plain, 2)
expect('carrier rows, all three sets', report.carrier_rows_with_refit, 10)
expect('no source column for one set', report.carrier_columns_plain, 5)
expect('a source column once there are three', report.carrier_columns_with_refit, 6)
expect('model curves drawn', report.curve_paths_with_refit, 6)
expect('step 5 draws nothing extra without a working answer',
       report.results_squares_plain, 0)
expect('step 5 draws the working answer beside the procedure',
       report.results_squares_with_working, 28)

// Two refits at two temperatures must both stand; a later one over the same
// temperature must win; undoing one must leave the other.
expect('two adjustments accumulate', Object.keys(twice.byT).length, 2)
expect('the settings carry both', Object.keys(asSettings(twice).fixed_counts).length, 2)
expect('the later adjustment wins', asSettings(overwritten).fixed_counts['5'][0], 1)
expect('the untouched one is left alone', asSettings(overwritten).fixed_counts['20'][0], 1)
expect('undoing leaves the rest', Object.keys(undoAt(twice, 5).byT).length, 1)
// A coupling is one band: undoing a sweep inside it drops it and returns the
// others to their pinned answers, so the screen and the settings agree.
expect('a coupling is recorded', coupledBand.couplings.length, 1)
expect('undoing inside a coupled band drops the coupling', undone.couplings.length, 0)
expect('and returns the rest to the pinned answer',
       Object.values(undone.byT).filter((one) => one.row !== one.pinned).length, 0)
expect('refitting inside a coupled band drops the coupling',
       refittedInside.couplings.length, 0)
expect('and the settings carry no band to re-couple it with',
       asSettings(refittedInside).smooth_band.length, 0)
expect('the refit stands where it was asked for',
       asSettings(refittedInside).fixed_counts['10'][0], 1)
expect('and the band it broke is back on its pinned answers',
       Object.values(refittedInside.byT).filter((one) => one.row !== one.pinned).length, 0)
// Split panels: one quantity becomes two plots, and the pair shares its axes.
expect('overlaid trends are two plots', panels(withRefit).length, 2)
expect('split trends are four', panels(trendsSplit).length, 4)
expect('the density pair shares its axes', sameAxes(trendsSplit, 0, 1), 1)
expect('the mobility pair shares its axes', sameAxes(trendsSplit, 2, 3), 1)
expect('overlaid curves are two plots', panels(curvesBoth).length, 2)
expect('split curves are four', panels(curvesSplit).length, 4)
expect('the rho_xx pair shares its axes', sameAxes(curvesSplit, 0, 1), 1)
expect('the rho_xy pair shares its axes', sameAxes(curvesSplit, 2, 3), 1)
// A split panel still draws both answers, one to a plot rather than both to one.
// Every sweep of this fixture is coupled, so the adjusted panel is crosses.
expect('the procedure panel draws the procedure',
       count(panels(trendsSplit)[0], '<circle') > 0 ? 1 : 0, 1)
expect('the adjusted panel draws the adjustment',
       count(panels(trendsSplit)[1], 'stroke-width="1.4"') > 0 ? 1 : 0, 1)
expect('and does not draw it over the other',
       count(panels(trendsSplit)[0], 'stroke-width="1.4"'), 0)

if (failures.length > 0) {
  // Thrown rather than exited: an uncaught throw leaves node with a non-zero
  // status just the same, and this file stays typed against the page's own
  // types without pulling in node's.
  throw new Error('render check failed: ' + failures.join('; '))
}
console.log('render check passed')
