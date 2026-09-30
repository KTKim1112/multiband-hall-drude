import { L } from '../labels'

export type Settings = {
  // The page runs the data rule only. The peaks rule stays on the command
  // line (--count peaks), for a reader with evidence outside transport.
  count: 'data'
  symmetrize_rhoxx: boolean
  antisymmetrize_rhoxy: boolean
  useDocument: boolean
  documentText: string
}

type Props = {
  settings: Settings
  onChange: (s: Settings) => void
  onBack: () => void
  onStart: () => void
  error: string | null
}

export function documentError(s: Settings): string | null {
  if (!s.useDocument) return null
  try {
    const parsed = JSON.parse(s.documentText)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? null : L.prelim_document_invalid
  } catch {
    return L.prelim_document_invalid
  }
}

export default function SettingsStep({ settings, onChange, onBack, onStart, error }: Props) {
  const set = (patch: Partial<Settings>) => onChange({ ...settings, ...patch })
  const docError = documentError(settings)

  return (
    <section className="panel">
      <h2>{L.settings_heading}</h2>
      <p className="lede">{L.settings_intro}</p>
      <ol className="procedure">
        {L.procedure_steps.map((step) => <li key={step}>{step}</li>)}
      </ol>
      <p className="note">{L.procedure_claim}</p>

      <h3>{L.sym_heading}</h3>
      <p className="note">{L.sym_intro}</p>
      <label className="check">
        <input id="sym-rhoxx" type="checkbox" checked={settings.symmetrize_rhoxx}
          onChange={(e) => set({ symmetrize_rhoxx: e.target.checked })} />
        <span>{L.sym_rhoxx}</span>
      </label>
      <label className="check">
        <input id="sym-rhoxy" type="checkbox" checked={settings.antisymmetrize_rhoxy}
          onChange={(e) => set({ antisymmetrize_rhoxy: e.target.checked })} />
        <span>{L.sym_rhoxy}</span>
      </label>

      <h3>{L.prelim_heading}</h3>
      <p className="note">{L.prelim_intro}</p>
      <label className="check">
        <input id="use-document" type="checkbox" checked={settings.useDocument}
          onChange={(e) => set({ useDocument: e.target.checked })} />
        <span>{L.prelim_document}</span>
      </label>
      {settings.useDocument && (
        <>
          <p className="note">{L.prelim_document_hint}</p>
          <textarea id="document-text" value={settings.documentText} onChange={(e) => set({ documentText: e.target.value })} />
          {docError && <div className="missing">{docError}</div>}
        </>
      )}

      {error && <div className="alert error">{error}</div>}
      <div className="actions">
        <button onClick={onBack}>{L.settings_back}</button>
        <button className="primary" disabled={docError !== null} onClick={onStart}>
          {L.settings_start}
        </button>
      </div>
    </section>
  )
}
