// Number formatting. No words here; words are in labels.ts.

export function sci(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return v.toExponential(digits - 1).replace('e+', 'e')
}

export function fixed(v: number | null | undefined, digits = 4): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return v.toFixed(digits)
}

export function general(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  const a = Math.abs(v)
  if (a !== 0 && (a >= 1e5 || a < 1e-3)) return sci(v)
  return String(Number(v.toPrecision(4)))
}

export function percent(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(digits)} %`
}
