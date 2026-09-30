// Which language the page speaks, and where every sentence comes from. FR-105.
//
// No component holds a sentence: they import `L` from here, and the wording
// lives in `text/ko.ts` and `text/en.ts`. `en.ts` is typed against `ko.ts`, so
// a label added to one and not the other fails the build.

import type { Progress } from './api'
import * as en from './text/en'
import * as ko from './text/ko'

export type Language = 'ko' | 'en'

const STORED = 'mbfit.language'

export function language(): Language {
  try {
    const saved = window.localStorage.getItem(STORED)
    if (saved === 'ko' || saved === 'en') return saved
  } catch {
    // A private window may refuse storage. The default is not worth failing for.
  }
  return 'ko'
}

export function setLanguage(next: Language): void {
  if (next === language()) return
  try {
    window.localStorage.setItem(STORED, next)
  } catch {
    // The choice will not outlive the tab, but the page can still turn.
  }
  // Every component reads `L` once, when its module loads, so the page is
  // rebuilt rather than re-rendered. That is simpler than threading a context
  // through two hundred labels, and costs nothing that matters: the analysis
  // runs on the server and a reload does not disturb it.
  window.location.reload()
}

const chosen = language() === 'en' ? en : ko

export const L = chosen.L

// Unit symbols are the same in both languages, so they are not translated.
export const FIELD_UNITS: [string, string][] = [
  ['T', 'T'], ['mT', 'mT'], ['kOe', 'kOe'], ['Oe', 'Oe'],
]
export const RESISTIVITY_UNITS: [string, string][] = [
  ['uOhm_cm', 'μΩ·cm'], ['mOhm_cm', 'mΩ·cm'], ['Ohm_cm', 'Ω·cm'], ['uOhm_m', 'μΩ·m'], ['Ohm_m', 'Ω·m'],
]

export function stageText(p: Progress): string {
  const T = p.T_K !== undefined ? `${p.T_K} K` : ''
  const combo = p.holes !== undefined ? `${p.holes}h+${p.electrons}e` : ''
  const stages = chosen.STAGES as Record<string, (p: Progress, T: string, combo: string) => string>
  const stage = p.stage ? stages[p.stage] : undefined
  return stage ? stage(p, T, combo) : chosen.STAGE_DEFAULT
}

export function errorText(code: string, params: Record<string, unknown> = {}): string {
  const messages = chosen.CODE_MESSAGES as Record<string, string>
  const template = messages[code] ?? chosen.UNKNOWN_CODE(code)
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = params[key]
    if (value === undefined || value === null) return '?'
    return Array.isArray(value) ? value.join(', ') : String(value)
  })
}
