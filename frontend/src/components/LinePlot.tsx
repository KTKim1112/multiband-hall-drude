// A small SVG plot: points and lines, linear or logarithmic axes.
// Hand-written rather than a plotting library, because the page needs four
// kinds of plot and a library would be most of the download (plan 001 6.1).

export type Series = {
  x: (number | null)[]
  y: (number | null)[]
  color: string
  label: string
  style: 'points' | 'line'
  // FR-109. A refit is drawn beside the answer the procedure reached, never
  // over it, so one plot carries up to three sets of the same quantity. Shape
  // separates the sets and colour keeps carrying the carrier sign, because a
  // reader who loses the sign has lost the thing the plot is about. Several
  // carriers of one sign share a temperature, so the sets are drawn as marks
  // and not as lines: a line through two holes at one temperature is a zigzag
  // that means nothing.
  marker?: 'circle' | 'square' | 'cross'
}

type Props = {
  series: Series[]
  title: string
  xLabel: string
  yLabel: string
  logY?: boolean
  logX?: boolean
  // Two panels of one quantity are only comparable on one pair of axes: side
  // by side on different scales, a change looks like whatever each panel's own
  // extent makes of it. A panel is handed the other's series here. They set the
  // range and are not drawn, so both come out on the same axes without either
  // panel having to know how a range is decided.
  alongside?: Series[]
}

const W = 460
const H = 300
const M = { left: 62, right: 14, top: 26, bottom: 44 }
const LEGEND_ROW = 13

function legendRows(labels: string[]): { x: number; y: number }[] {
  // Laid out left to right under the title and wrapped, because the number of
  // series is no longer two: a refit and a coupling add their own.
  const room = W - M.left - M.right
  const places: { x: number; y: number }[] = []
  let x = 0
  let row = 0
  for (const label of labels) {
    const width = 26 + label.length * 6.4
    if (x > 0 && x + width > room) { row += 1; x = 0 }
    places.push({ x: M.left + x, y: 30 + row * LEGEND_ROW })
    x += width
  }
  return places
}

function markAt(a: number, b: number, shape: 'circle' | 'square' | 'cross', color: string, key: number) {
  if (shape === 'square') {
    return <rect key={key} x={a - 2.2} y={b - 2.2} width={4.4} height={4.4} fill={color} opacity={0.8} />
  }
  if (shape === 'cross') {
    return (
      <g key={key} stroke={color} strokeWidth={1.4} opacity={0.9}>
        <line x1={a - 2.8} x2={a + 2.8} y1={b - 2.8} y2={b + 2.8} />
        <line x1={a - 2.8} x2={a + 2.8} y1={b + 2.8} y2={b - 2.8} />
      </g>
    )
  }
  return <circle key={key} cx={a} cy={b} r={2.2} fill={color} opacity={0.75} />
}

function finite(v: number | null | undefined): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

function niceTicks(lo: number, hi: number, count = 5): number[] {
  if (!(hi > lo)) return [lo]
  const raw = (hi - lo) / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  const ticks: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) {
    ticks.push(Math.abs(v) < step * 1e-9 ? 0 : v)
  }
  return ticks
}

function formatTick(v: number, log: boolean): string {
  if (log) return `1e${Math.round(Math.log10(v))}`
  const a = Math.abs(v)
  if (a !== 0 && (a >= 1e4 || a < 1e-2)) return v.toExponential(0)
  return String(Number(v.toPrecision(4)))
}

export default function LinePlot({
  series, title, xLabel, yLabel, logY = false, logX = false, alongside,
}: Props) {
  const keep = (x: number | null, y: number | null | undefined) =>
    finite(x) && finite(y) && (!logY || y > 0) && (!logX || x > 0)
  const xs: number[] = []
  const ys: number[] = []
  for (const s of [...series, ...(alongside ?? [])]) {
    s.x.forEach((x, i) => {
      const y = s.y[i]
      if (keep(x, y)) {
        xs.push(logX ? Math.log10(x as number) : (x as number))
        ys.push(logY ? Math.log10(y as number) : (y as number))
      }
    })
  }
  if (xs.length === 0) {
    return (
      <svg className="plot" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
        <text className="title" x={M.left} y={16}>{title}</text>
      </svg>
    )
  }

  let [x0, x1] = [Math.min(...xs), Math.max(...xs)]
  let [y0, y1] = [Math.min(...ys), Math.max(...ys)]
  if (x1 === x0) { x0 -= logX ? 0.5 : 1; x1 += logX ? 0.5 : 1 }
  if (y1 === y0) { y0 -= logY ? 0.5 : Math.abs(y0) * 0.1 || 1; y1 += logY ? 0.5 : Math.abs(y1) * 0.1 || 1 }
  const padY = (y1 - y0) * 0.06
  y0 -= padY
  y1 += padY

  // The legend sits under the title, so the drawing starts below whatever
  // number of rows it took. Two series still take one row and the plot looks
  // as it did; a refit and a coupling take two and the plot gives way.
  const places = legendRows(series.map((s) => s.label))
  const rows = places.length === 0 ? 0 : (Math.max(...places.map((q) => q.y)) - 30) / LEGEND_ROW + 1
  const top = M.top + rows * LEGEND_ROW

  const px = (x: number) => M.left + ((x - x0) / (x1 - x0)) * (W - M.left - M.right)
  const py = (y: number) => H - M.bottom - ((y - y0) / (y1 - y0)) * (H - top - M.bottom)

  const xTicks = logX
    ? Array.from({ length: Math.floor(x1) - Math.ceil(x0) + 1 }, (_, i) => Math.ceil(x0) + i)
    : niceTicks(x0, x1)
  const yTicks = logY
    ? Array.from({ length: Math.floor(y1) - Math.ceil(y0) + 1 }, (_, i) => Math.ceil(y0) + i)
    : niceTicks(y0, y1)

  return (
    <svg className="plot" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
      <text className="title" x={M.left} y={16}>{title}</text>
      {yTicks.map((t) => (
        <g key={`y${t}`}>
          <line className="grid" x1={M.left} x2={W - M.right} y1={py(t)} y2={py(t)} />
          <text x={M.left - 6} y={py(t) + 4} textAnchor="end">
            {formatTick(logY ? 10 ** t : t, logY)}
          </text>
        </g>
      ))}
      {xTicks.map((t) => (
        <g key={`x${t}`}>
          <line className="axis" x1={px(t)} x2={px(t)} y1={H - M.bottom} y2={H - M.bottom + 4} />
          <text x={px(t)} y={H - M.bottom + 16} textAnchor="middle">
            {formatTick(logX ? 10 ** t : t, logX)}
          </text>
        </g>
      ))}
      <line className="axis" x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} />
      <line className="axis" x1={M.left} x2={M.left} y1={top} y2={H - M.bottom} />
      <text x={(M.left + W - M.right) / 2} y={H - 8} textAnchor="middle">{xLabel}</text>
      <text transform={`translate(14 ${(M.top + H - M.bottom) / 2}) rotate(-90)`} textAnchor="middle">
        {yLabel}
      </text>

      {series.map((s, k) => {
        const points: [number, number][] = []
        s.x.forEach((x, i) => {
          const y = s.y[i]
          if (keep(x, y)) {
            points.push([px(logX ? Math.log10(x as number) : (x as number)),
                         py(logY ? Math.log10(y as number) : (y as number))])
          }
        })
        if (s.style === 'line') {
          const d = points.map(([a, b], i) => `${i ? 'L' : 'M'}${a.toFixed(1)} ${b.toFixed(1)}`).join('')
          return <path key={k} d={d} fill="none" stroke={s.color} strokeWidth={1.8} />
        }
        const shape = s.marker ?? 'circle'
        return <g key={k}>{points.map(([a, b], i) => markAt(a, b, shape, s.color, i))}</g>
      })}

      {series.map((s, k) => (
        // Under the title, not over the data: marks can sit anywhere in the plot.
        <g key={`legend${k}`} transform={`translate(${places[k].x} ${places[k].y})`}>
          {s.style === 'line'
            ? <line x1={0} x2={16} y1={0} y2={0} stroke={s.color} strokeWidth={2} />
            : markAt(8, 0, s.marker ?? 'circle', s.color, 0)}
          <text x={22} y={4}>{s.label}</text>
        </g>
      ))}
    </svg>
  )
}
