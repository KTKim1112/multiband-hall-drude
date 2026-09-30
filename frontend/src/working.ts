// FR-112. The answer a reader is building on the adjustment step.
//
// Adjustments accumulate a temperature at a time: each covers the sweeps it
// names and leaves the rest as the procedure decided them, so a series can be
// repaired piece by piece. Where two cover one temperature the later stands.
//
// Kept as plain data and changed only by the functions below, because two
// things have to agree exactly: what the page draws, and the settings the
// confirm is asked for. The confirm sends settings and the procedure runs
// again under them, so a working answer that cannot be written down as
// settings is a working answer the reader cannot keep.

import type { BandResult, Coupling, TemperatureResult } from './api'

export type Adjusted = {
  /** The answer now standing for this sweep: pinned, or coupled if one ran. */
  row: TemperatureResult
  holes: number
  electrons: number
  /** The pinned answer, kept so a coupling's price can still be shown. */
  pinned: TemperatureResult
}

export type Working = {
  byT: Record<string, Adjusted>
  /** In the order they were asked for, which is part of what the reader did. */
  couplings: { range: string; strength: string }[]
}

export const EMPTY: Working = { byT: {}, couplings: [] }

const key = (T: number) => String(T)

/** How a band of temperatures is written in a configuration document. */
export function rangeOf(temperatures: number[]): string {
  if (temperatures.length === 0) return ''
  const low = Math.min(...temperatures)
  const high = Math.max(...temperatures)
  return low === high ? String(low) : `${low}-${high}`
}

export function isEmpty(working: Working): boolean {
  return Object.keys(working.byT).length === 0
}

export function countAt(working: Working, T: number): Adjusted | null {
  return working.byT[key(T)] ?? null
}

/** A refit: every sweep it covers now carries the count the reader chose. */
export function withRefit(
  working: Working, refit: BandResult, holes: number, electrons: number,
): Working {
  const byT = { ...working.byT }
  // FR-109. A sweep where the count would not fit is not an adjustment. The
  // row that came back for it is the procedure's own answer, and recording it
  // as pinned would put a count into the confirmed document that the procedure
  // has already shown it cannot honour.
  const unheld = new Set(refit.unheld ?? [])
  const held: number[] = []
  for (const row of refit.temperatures) {
    if (unheld.has(row.T)) continue
    byT[key(row.T)] = { row, holes, electrons, pinned: row }
    held.push(row.T)
  }
  // FR-112, and the same rule `without` follows: a band half adjusted is not
  // one series (FR-090). A refit inside a coupling therefore ends the
  // coupling, and the sweeps it covered fall back to their pinned answers.
  // Leaving it standing would send a stale band to the confirm -- which the
  // procedure refuses outright where the refit changed the count, and which
  // silently re-couples a sweep the page is drawing as independent where it
  // did not.
  const inside = (one: { range: string }) => held.some((T) => covers(one.range, T))
  const dropped = working.couplings.filter(inside)
  const couplings = working.couplings.filter((one) => !inside(one))
  for (const one of dropped) {
    for (const [at, was] of Object.entries(byT)) {
      if (covers(one.range, Number(at))) byT[at] = { ...was, row: was.pinned }
    }
  }
  return { byT, couplings }
}

/**
 * A coupling: the same sweeps, refined as one series. The pinned answer stays
 * beside it so that what the coupling cost is still readable.
 */
export function withCoupling(working: Working, coupled: Coupling): Working {
  const byT = { ...working.byT }
  const covered: number[] = []
  for (const row of coupled.temperatures) {
    const was = byT[key(row.T)]
    if (!was) continue
    byT[key(row.T)] = { ...was, row }
    covered.push(row.T)
  }
  const range = rangeOf(covered)
  const couplings = working.couplings
    .filter((one) => one.range !== range)
    .concat([{ range, strength: coupled.strength }])
  return { byT, couplings }
}

/**
 * Undo everything covering one sweep, leaving the procedure's answer there.
 *
 * A coupling that covered it goes with it -- a band half adjusted is not one
 * series (FR-090) -- and the other sweeps of that band fall back to their
 * pinned answers. Leaving them coupled would put a number on the screen that
 * the settings no longer ask for, and the confirm would then disagree with
 * what the reader was looking at when they pressed it.
 */
export function without(working: Working, T: number): Working {
  const byT = { ...working.byT }
  delete byT[key(T)]
  const dropped = working.couplings.filter((one) => covers(one.range, T))
  const couplings = working.couplings.filter((one) => !covers(one.range, T))
  for (const one of dropped) {
    for (const [at, was] of Object.entries(byT)) {
      if (covers(one.range, Number(at))) byT[at] = { ...was, row: was.pinned }
    }
  }
  return { byT, couplings }
}

function covers(range: string, T: number): boolean {
  const [low, high] = range.includes('-')
    ? range.split('-').map(Number)
    : [Number(range), Number(range)]
  return T >= low && T <= high
}

/**
 * What the plots draw. Shaped as a `BandResult` so that `Trends`, `Curves` and
 * `Carriers` take it exactly as they take a single refit -- the working answer
 * is shown beside the procedure's, never in place of it (FR-109).
 */
export function asBand(working: Working, mode: string): BandResult | null {
  const rows = Object.values(working.byT)
  if (rows.length === 0) return null
  const ordered = [...rows].sort((a, b) => a.row.T - b.row.T)
  const coupled = ordered.filter((one) => one.row !== one.pinned)
  const smoothing: Coupling | null = coupled.length === 0 ? null : {
    strength: working.couplings[working.couplings.length - 1]?.strength ?? '',
    lambda: 0,
    roughness: null,
    temperatures: coupled.map((one) => one.row),
  }
  return {
    mode: mode as BandResult['mode'],
    seconds: 0,
    // The pinned answer is the set drawn as the refit; a coupled sweep is
    // drawn again in the coupled set, which is how all three read at once.
    temperatures: ordered.map((one) => one.pinned),
    roughness: null,
    smoothing,
    // Empty by construction: a sweep the count could not be fitted at is
    // never entered here, so the accumulated answer holds only what was held.
    unheld: [],
  }
}

/**
 * The settings the adjustments amount to, which is what a confirm is asked
 * for. One entry per sweep rather than an inferred range: the page has already
 * resolved which adjustment stands where, and a range guessed back out of that
 * could differ from what the reader did.
 */
export function asSettings(working: Working): {
  fixed_counts: Record<string, number[]>
  smooth_band: { range: string; strength: string }[]
} {
  const fixed_counts: Record<string, number[]> = {}
  for (const [T, one] of Object.entries(working.byT)) {
    fixed_counts[T] = [one.holes, one.electrons]
  }
  return { fixed_counts, smooth_band: working.couplings.map((one) => ({ ...one })) }
}
