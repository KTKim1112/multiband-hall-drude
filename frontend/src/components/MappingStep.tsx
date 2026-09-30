import type { Mapping, Preview } from '../api'
import { FIELD_UNITS, L, RESISTIVITY_UNITS } from '../labels'

type Props = {
  previews: Preview[]
  mappings: Record<string, Mapping>
  onChange: (fileId: string, mapping: Mapping) => void
  onBack: () => void
  onNext: () => void
}

export function mappingFrom(preview: Preview): Mapping {
  const p = preview.proposal
  return {
    file_id: preview.file_id,
    B: p.B,
    rhoxx: p.rhoxx,
    rhoxy: p.rhoxy,
    T_column: p.T_column,
    T_K: p.T_column ? null : p.T_from_name,
    field_unit: p.field_unit,
    resistivity_unit: p.resistivity_unit,
  }
}

export function missingOf(m: Mapping | undefined): string[] {
  if (!m) return [L.mapping_B, L.mapping_rhoxx, L.mapping_rhoxy, L.mapping_T_source]
  const missing: string[] = []
  if (!m.B) missing.push(L.mapping_B)
  // One channel per file is enough; the other may come from another file at
  // the same temperature, and the server says so if it does not.
  if (!m.rhoxx && !m.rhoxy) missing.push(`${L.mapping_rhoxx} / ${L.mapping_rhoxy}`)
  if (!m.T_column && (m.T_K === null || !Number.isFinite(m.T_K))) missing.push(L.mapping_T_source)
  return missing
}

function ColumnSelect({ value, columns, onChange }: {
  value: string | null; columns: string[]; onChange: (v: string | null) => void
}) {
  return (
    <select value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">{L.mapping_choose}</option>
      {columns.map((c) => <option key={c} value={c}>{c}</option>)}
    </select>
  )
}

function FileCard({ preview, mapping, onChange }: {
  preview: Preview; mapping: Mapping; onChange: (m: Mapping) => void
}) {
  const set = (patch: Partial<Mapping>) => onChange({ ...mapping, ...patch })
  const fromColumn = mapping.T_column !== null
  const missing = missingOf(mapping)

  return (
    <div className="file-card">
      <h3>{preview.name}</h3>
      <div className="note">
        {L.mapping_skipped(preview.skipped_lines)} · {L.mapping_rows(preview.rows.length, preview.row_count)}
        {preview.proposal.T_from_name !== null && !fromColumn && <> · {L.mapping_T_from_name(preview.proposal.T_from_name)}</>}
      </div>
      <div className="scroll">
        <table>
          <thead><tr>{preview.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {preview.rows.map((row, i) => (
              <tr key={i}>{row.map((cell, j) => <td key={j} className="num">{cell}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mapping-grid">
        <label>{L.mapping_B}<ColumnSelect value={mapping.B} columns={preview.columns} onChange={(v) => set({ B: v })} /></label>
        <label>{L.mapping_rhoxx}<ColumnSelect value={mapping.rhoxx} columns={preview.columns} onChange={(v) => set({ rhoxx: v })} /></label>
        <label>{L.mapping_rhoxy}<ColumnSelect value={mapping.rhoxy} columns={preview.columns} onChange={(v) => set({ rhoxy: v })} /></label>
        <label>{L.mapping_T_source}
          <select
            value={fromColumn ? 'column' : 'value'}
            onChange={(e) => e.target.value === 'column'
              ? set({ T_column: preview.proposal.T_column ?? preview.columns[0] ?? null, T_K: null })
              : set({ T_column: null, T_K: preview.proposal.T_from_name })}
          >
            <option value="value">{L.mapping_T_value}</option>
            <option value="column">{L.mapping_T_from_column}</option>
          </select>
        </label>
        {fromColumn ? (
          <label>{L.mapping_T_column}<ColumnSelect value={mapping.T_column} columns={preview.columns} onChange={(v) => set({ T_column: v })} /></label>
        ) : (
          <label>{L.mapping_T_value}
            <input type="number" step="any" value={mapping.T_K ?? ''}
              onChange={(e) => set({ T_K: e.target.value === '' ? null : Number(e.target.value) })} />
          </label>
        )}
        <label>{L.mapping_field_unit}
          <select value={mapping.field_unit} onChange={(e) => set({ field_unit: e.target.value })}>
            {FIELD_UNITS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        </label>
        <label>{L.mapping_resistivity_unit}
          <select value={mapping.resistivity_unit} onChange={(e) => set({ resistivity_unit: e.target.value })}>
            {RESISTIVITY_UNITS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        </label>
      </div>
      {missing.length > 0 && <div className="missing">{L.mapping_missing(missing.join(', '))}</div>}
    </div>
  )
}

export default function MappingStep({ previews, mappings, onChange, onBack, onNext }: Props) {
  const complete = previews.every((p) => missingOf(mappings[p.file_id]).length === 0)
  return (
    <section className="panel">
      <h2>{L.mapping_heading}</h2>
      <p className="lede">{L.mapping_intro}</p>
      {previews.map((p) => (
        <FileCard key={p.file_id} preview={p} mapping={mappings[p.file_id] ?? mappingFrom(p)}
          onChange={(m) => onChange(p.file_id, m)} />
      ))}
      <div className="actions">
        <button onClick={onBack}>{L.mapping_back}</button>
        <button className="primary" disabled={!complete} onClick={onNext}>{L.mapping_next}</button>
      </div>
    </section>
  )
}
