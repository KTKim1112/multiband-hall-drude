import { useState } from 'react'
import { ApiFailure, startAnalysis, stopJob, type AnalysisResult, type Mapping, type Preview } from './api'
import FilesStep from './components/FilesStep'
import MappingStep, { mappingFrom } from './components/MappingStep'
import OfflineNotice from './components/OfflineNotice'
import Results from './components/Results'
import RunPanel from './components/RunPanel'
import SettingsStep, { type Settings } from './components/SettingsStep'
import { L, errorText, language, setLanguage, type Language } from './labels'
import AdjustStep from './components/AdjustStep'
import { EMPTY, asBand, type Working } from './working'
import { usePoll } from './usePoll'
import { useServer } from './useServer'

type Step = 'files' | 'mapping' | 'settings' | 'run' | 'adjust'

const INITIAL_SETTINGS: Settings = {
  count: 'data',               // FR-099: the rule that needs no evidence beyond the sweep
  symmetrize_rhoxx: false,    // FR-100
  antisymmetrize_rhoxy: false,
  useDocument: false,
  documentText: '',
}

export default function App() {
  const [step, setStep] = useState<Step>('files')
  const [previews, setPreviews] = useState<Preview[]>([])
  const [mappings, setMappings] = useState<Record<string, Mapping>>({})
  const [settings, setSettings] = useState<Settings>(INITIAL_SETTINGS)
  const [startError, setStartError] = useState<string | null>(null)
  // FR-112. The working answer lives here, not inside a step: React unmounts
  // the branch it is not rendering, so state held in either step would be
  // destroyed the moment the reader walks between them.
  const [working, setWorking] = useState<Working>(EMPTY)
  const [jobId, setJobId] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const { job, failure } = usePoll<AnalysisResult>(jobId)
  const server = useServer()

  function addPreviews(added: Preview[]) {
    setPreviews((old) => [...old, ...added])
    setMappings((old) => {
      const next = { ...old }
      for (const p of added) next[p.file_id] = mappingFrom(p)
      return next
    })
  }

  async function start() {
    setStartError(null)
    try {
      const response = await startAnalysis({
        files: previews.map((p) => mappings[p.file_id] ?? mappingFrom(p)),
        count: settings.count,
        symmetrize_rhoxx: settings.symmetrize_rhoxx,
        antisymmetrize_rhoxy: settings.antisymmetrize_rhoxy,
        document: settings.useDocument ? JSON.parse(settings.documentText) : null,
      })
      setStopping(false)
      setJobId(response.job_id)
      setStep('run')
    } catch (e) {
      const f = e instanceof ApiFailure ? e : new ApiFailure({ code: 'E_INTERNAL', params: {} })
      setStartError(errorText(f.code, f.params))
    }
  }

  function reset() {
    setJobId(null)
    setStep('files')
    setPreviews([])
    setMappings({})
    setSettings(INITIAL_SETTINGS)
    setWorking(EMPTY)
  }

  const finished = job && (job.state === 'succeeded' || job.state === 'stopped' || job.state === 'failed')
  const stepIndex = {
    files: 0, mapping: 1, settings: 2, run: finished ? 4 : 3, adjust: 5,
  }[step]
  const names = [L.step_files, L.step_mapping, L.step_settings, L.step_run,
                 L.step_results, L.step_adjust]

  return (
    <div className="page">
      <header className="top">
        <h1>{L.title}</h1>
        <p>{L.lede}</p>
        {/* FR-105. Changing this rebuilds the page: every label is read once at
            module load. Nothing is lost by it -- the analysis is on the server. */}
        <label className="note">
          {L.language_label}{' '}
          <select value={language()}
            onChange={(e) => setLanguage(e.target.value as Language)}>
            <option value="ko">{L.language_ko}</option>
            <option value="en">{L.language_en}</option>
          </select>
        </label>
      </header>
      <ol className="steps">
        {names.map((name, i) => (
          <li key={name} className={i === stepIndex ? 'current' : i < stepIndex ? 'done' : ''}>{name}</li>
        ))}
      </ol>

      {/* FR-108. While the program is gone the steps are shown for what they
          are -- unusable -- rather than failing one click at a time. */}
      {!server.answering ? (
        <OfflineNotice checking={server.checking} onCheck={server.check} />
      ) : (
        <>
          {step === 'files' && (
            <FilesStep previews={previews} onAdd={addPreviews}
              onRemove={(id) => setPreviews((old) => old.filter((p) => p.file_id !== id))}
              onNext={() => setStep('mapping')} />
          )}
          {step === 'mapping' && (
            <MappingStep previews={previews} mappings={mappings}
              onChange={(id, m) => setMappings((old) => ({ ...old, [id]: m }))}
              onBack={() => setStep('files')} onNext={() => setStep('settings')} />
          )}
          {step === 'settings' && (
            <SettingsStep settings={settings} onChange={setSettings} error={startError}
              onBack={() => setStep('mapping')} onStart={() => void start()} />
          )}
          {step === 'adjust' && jobId && job?.state === 'succeeded' && job.result && (
            // A stopped analysis never reaches the context an adjustment reads
            // from, so the step is offered only for one that finished.
            <AdjustStep analysisId={jobId} result={job.result} working={working}
              onChange={setWorking} onBack={() => setStep('run')} />
          )}
          {step === 'run' && (
            <>
              {failure && <div className="alert error">{errorText(failure.code, failure.params)}</div>}
              {(!job || job.state === 'pending' || job.state === 'running') && (
                <RunPanel progress={job?.progress ?? {}} stopping={stopping}
                  onStop={() => { setStopping(true); if (jobId) void stopJob(jobId) }} />
              )}
              {job?.state === 'failed' && (
                <section className="panel">
                  <div className="alert error">
                    {L.results_failed} {job.error ? errorText(job.error.code, job.error.params) : ''}
                  </div>
                  <div className="actions">
                    <button onClick={() => setStep('settings')}>{L.mapping_next}</button>
                    <button onClick={reset}>{L.results_new}</button>
                  </div>
                </section>
              )}
              {job && (job.state === 'succeeded' || job.state === 'stopped') && job.result && jobId && (
                <Results jobId={jobId} state={job.state} result={job.result}
                  preliminary={job.preliminary} onNew={reset}
                  refit={asBand(working, job.result.mode)}
                  onAdjust={() => setStep('adjust')} />
              )}
              {job?.state === 'stopped' && !job.result && (
                <section className="panel">
                  <div className="alert warn">{L.results_stopped}</div>
                  <div className="actions"><button onClick={reset}>{L.results_new}</button></div>
                </section>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
