// The server's contract, data model 005 section 1. Every failure arrives as a
// code and parameters; turning it into a sentence is labels.ts's job alone.

export type Proposal = {
  B: string | null
  rhoxx: string | null
  rhoxy: string | null
  T_column: string | null
  T_from_name: number | null
  field_unit: string
  resistivity_unit: string
}

export type Preview = {
  file_id: string
  name: string
  skipped_lines: number
  columns: string[]
  rows: string[][]
  row_count: number
  proposal: Proposal
  temperatures: number[]
}

export type Mapping = {
  file_id: string
  B: string | null
  rhoxx: string | null
  rhoxy: string | null
  T_column: string | null
  T_K: number | null
  field_unit: string
  resistivity_unit: string
}

export type Carrier = {
  name: string
  kind: 'hole' | 'electron'
  n: number | null
  mu: number | null
  share: number | null
}

export type CandidateRow = {
  h: number
  e: number
  rmsexx: number | null
  condition: number | null
  spread: number | null
  share: number | null
  bound: boolean
  expired: boolean
  starts: number
  seconds: number
}

export type SpectrumBranch = {
  mobility_cm2Vs: number[]
  weight: number[]
  peaks_cm2Vs: number[]
}

export type Curve = {
  B: (number | null)[]
  xx: (number | null)[]
  xy: (number | null)[]
  fxx: (number | null)[]
  fxy: (number | null)[]
}

export type TemperatureResult = {
  T: number
  mode: 'data' | 'peaks'
  label: string
  grade: string
  r2xx: number | null
  r2xy: number | null
  rmsexx: number | null
  rmsexy: number | null
  condition: number | null
  spread: number | null
  failed: string[]
  escaped: string[]
  undetermined: string
  undetermined_ratio: number | null
  // FR-090. The count both neighbours share where this sweep carries more, and
  // what holding it to theirs costs in residual.
  island: string
  island_price: number | null
  // FR-081. The mobility spectrum this sweep's search was bounded by. The
  // vertical axis is the normalised weight the spectrum solves for, not a
  // carrier density.
  spectrum: {
    hole: SpectrumBranch
    electron: SpectrumBranch
  } | null
  window: Record<string, (number | null)[]>
  beyond: boolean
  ratio_xx: number | null
  ratio_xy: number | null
  runs_xx: number | null
  iterations: number
  stop: string
  seconds: number
  carriers: Carrier[]
  candidates: CandidateRow[]
  curve: Curve | null
}

export type AnalysisResult = {
  mode: 'data' | 'peaks'
  seconds: number
  temperatures: TemperatureResult[]
  // FR-005. Rows the server discarded while combining the uploads, before the
  // library saw the table. Absent on an answer assembled on the page.
  dropped_before_fit?: number
}

// FR-025. A refit of a band also reports how far that band is from a smooth
// series. The coupling is a separate answer, folded in here once it arrives.
export type Coupling = {
  strength: string
  lambda: number
  roughness: number | null
  temperatures: TemperatureResult[]
}

export type BandResult = AnalysisResult & {
  roughness: number | null
  smoothing: Coupling | null
  // FR-109. Sweeps where no starting point finished inside the budget, so the
  // count was not applied and the procedure's own answer still stands there.
  unheld: number[]
}

export type Progress = {
  stage?: string
  T_K?: number
  index?: number
  total?: number
  holes?: number
  electrons?: number
  max_holes?: number
  max_electrons?: number
  iteration?: number
  done?: number
  // A coupled fit of a band is one call to the optimiser, so it is counted in
  // starts and in elapsed against its budget (AC-039), not in temperatures.
  start?: number
  starts?: number
  evaluations?: number
  seconds?: number
  budget?: number | null
}

export type JobState = 'pending' | 'running' | 'succeeded' | 'failed' | 'stopped'

export type PreliminaryCarrier = {
  name: string
  kind: 'hole' | 'electron'
  density_cm3: number
  mobility_cm2Vs: number
}

export type ApiError = { code: string; params: Record<string, unknown> }

export type Job<R> = {
  job_id: string
  kind: 'analysis' | 'precise' | 'recount'
  state: JobState
  progress: Progress
  error: ApiError | null
  result: R | null
  preliminary: PreliminaryCarrier[] | null
}

export type Interval = {
  quantity: string
  value: number | null
  low: number | null
  high: number | null
  one_sigma: number | null
  relative_one_sigma: number | null
}

export type PreciseResult = {
  T_K: number
  resamples: number
  block_length: number
  seed: number
  lower_bound: boolean
  parameters: Interval[]
  derived: Interval[]
}

export type AnalysisRequest = {
  files: Mapping[]
  count: 'data' | 'peaks'
  symmetrize_rhoxx: boolean
  antisymmetrize_rhoxy: boolean
  document: Record<string, unknown> | null
}

export class ApiFailure extends Error {
  code: string
  params: Record<string, unknown>
  constructor(error: ApiError) {
    super(error.code)
    this.code = error.code
    this.params = error.params ?? {}
  }
}

async function call<T>(input: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(input, init)
  } catch {
    throw new ApiFailure({ code: 'E_NETWORK', params: {} })
  }
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  if (!response.ok) {
    const error = body as ApiError | null
    throw new ApiFailure(
      error && typeof error.code === 'string'
        ? error
        : { code: 'E_INTERNAL', params: { status: response.status } },
    )
  }
  return body as T
}

// FR-108. The one call the page makes to ask whether the program is there at
// all; a failure here is about the program, not about the reader's data.
export function health(): Promise<{ version: string }> {
  return call('/api/health')
}

export function uploadFiles(files: File[]): Promise<{ files: Preview[] }> {
  const form = new FormData()
  for (const file of files) form.append('files', file, file.name)
  return call('/api/files', { method: 'POST', body: form })
}

function json(body: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export function startAnalysis(request: AnalysisRequest): Promise<{ job_id: string }> {
  return call('/api/analyses', json(request))
}

export function getJob<R>(jobId: string): Promise<Job<R>> {
  return call(`/api/jobs/${jobId}`)
}

export function stopJob(jobId: string): Promise<{ job_id: string }> {
  return call(`/api/jobs/${jobId}/stop`, { method: 'POST' })
}

export function startPrecise(jobId: string, T_K: number): Promise<{ job_id: string }> {
  return call(`/api/jobs/${jobId}/precise`, json({ T_K }))
}

// FR-109. A sweep or a band of them, refitted at a count the reader chose. The
// answer has the shape an analysis has, so one temperature and twelve are the
// same shape and the page draws both with the components it already has.
export function startRecount(
  jobId: string, temperatures: number[], holes: number, electrons: number,
): Promise<{ job_id: string }> {
  return call(`/api/jobs/${jobId}/recount`, json({ temperatures, holes, electrons }))
}

// FR-109, amended. The coupling is asked of a refit that has already answered.
// It was once the tail of the refit's own request, and a coupling over a long
// band takes far longer than the refits it follows, so asking for one withheld
// the refit that was already complete.
export function startSmooth(
  recountJobId: string, strength: string,
): Promise<{ job_id: string }> {
  return call(`/api/jobs/${recountJobId}/smooth`, json({ strength }))
}

// FR-112. Settings, not the numbers on the page: the procedure runs again
// under them, which is what makes the files that come back the command line's.
export function startConfirm(
  jobId: string,
  fixed_counts: Record<string, number[]>,
  smooth_band: { range: string; strength: string }[],
): Promise<{ job_id: string }> {
  return call(`/api/jobs/${jobId}/confirm`, json({ fixed_counts, smooth_band }))
}

export const reportUrl = (jobId: string) => `/api/jobs/${jobId}/report.html`
export const tablesUrl = (jobId: string) => `/api/jobs/${jobId}/tables.zip`
