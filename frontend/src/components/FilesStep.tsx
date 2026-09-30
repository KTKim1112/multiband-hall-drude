import { useEffect, useRef, useState } from 'react'
import { ApiFailure, uploadFiles, type Preview } from '../api'
import { L, errorText } from '../labels'

type Props = {
  previews: Preview[]
  onAdd: (added: Preview[]) => void
  onRemove: (fileId: string) => void
  onNext: () => void
}

const TABLE_FILE = /\.(csv|txt|dat|tsv|xlsx?)$/i

// Entries of a drop, read synchronously: the DataTransfer is gone once the
// event handler returns, the entries are not.
type Entry = {
  isFile: boolean
  isDirectory: boolean
  file: (ok: (f: File) => void, fail: (e: unknown) => void) => void
  createReader: () => { readEntries: (ok: (e: Entry[]) => void, fail: (e: unknown) => void) => void }
}

function entriesOf(transfer: DataTransfer): Entry[] {
  const out: Entry[] = []
  for (const item of Array.from(transfer.items ?? [])) {
    const entry = item.webkitGetAsEntry?.() as unknown as Entry | null
    if (entry) out.push(entry)
  }
  return out
}

async function filesOf(entries: Entry[]): Promise<File[]> {
  const out: File[] = []
  async function walk(entry: Entry): Promise<void> {
    if (entry.isFile) {
      out.push(await new Promise<File>((ok, fail) => entry.file(ok, fail)))
    } else if (entry.isDirectory) {
      const reader = entry.createReader()
      for (;;) {
        const batch = await new Promise<Entry[]>((ok, fail) => reader.readEntries(ok, fail))
        if (batch.length === 0) break
        for (const child of batch) await walk(child)
      }
    }
  }
  for (const entry of entries) await walk(entry)
  return out
}

type Conflict = { one: Preview; others: Preview[]; temperatures: number[] }

// FR-096. Two files holding the same channel at the same temperature. The
// reference folder holds twelve files and a table of all twelve; choosing
// everything in it must say so here, not three steps later.
export function conflictOf(previews: Preview[]): Conflict | null {
  const channels = (p: Preview) => ({ xx: !!p.proposal.rhoxx, xy: !!p.proposal.rhoxy })
  const clash = (a: Preview, b: Preview) => {
    const ca = channels(a)
    const cb = channels(b)
    if (!((ca.xx && cb.xx) || (ca.xy && cb.xy))) return []
    const tb = new Set(b.temperatures)
    return a.temperatures.filter((t) => tb.has(t))
  }
  let best: Conflict | null = null
  for (const one of previews) {
    const others: Preview[] = []
    const shared = new Set<number>()
    for (const other of previews) {
      if (other === one) continue
      const common = clash(one, other)
      if (common.length) {
        others.push(other)
        common.forEach((t) => shared.add(t))
      }
    }
    if (others.length && (!best || others.length > best.others.length)) {
      best = { one, others, temperatures: [...shared].sort((a, b) => a - b) }
    }
  }
  return best
}

export default function FilesStep({ previews, onAdd, onRemove, onNext }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const folder = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [skipped, setSkipped] = useState(0)

  async function send(list: FileList | File[] | null) {
    const all = list ? Array.from(list) : []
    const chosen = all.filter((f) => TABLE_FILE.test(f.name))
    setSkipped(all.length - chosen.length)
    if (chosen.length === 0) return
    setBusy(true)
    setErrors([])
    // One file at a time, so a file the server cannot read does not stop the
    // rest, and each refusal names its own file.
    const failed: string[] = []
    for (const file of chosen) {
      try {
        const response = await uploadFiles([file])
        onAdd(response.files)
      } catch (e) {
        const f = e instanceof ApiFailure ? e : new ApiFailure({ code: 'E_INTERNAL', params: {} })
        failed.push(errorText(f.code, { file: file.name, ...f.params }))
      }
    }
    setErrors(failed)
    setBusy(false)
    if (input.current) input.current.value = ''
    if (folder.current) folder.current.value = ''
  }

  // Files and folders dropped anywhere on the page count, not only on the
  // zone. Left to itself the browser opens a file dropped elsewhere as a new
  // page, and the reader sees the program ignore it.
  useEffect(() => {
    const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes('Files')
    const onDragOver = (e: DragEvent) => { if (hasFiles(e)) { e.preventDefault(); setOver(true) } }
    const onDragLeave = (e: DragEvent) => { if (e.relatedTarget === null) setOver(false) }
    const onDrop = (e: DragEvent) => {
      if (!hasFiles(e) || !e.dataTransfer) return
      e.preventDefault()
      setOver(false)
      const entries = entriesOf(e.dataTransfer)
      if (entries.length === 0) {
        void send(e.dataTransfer.files)
        return
      }
      void filesOf(entries).then(send, () => send(e.dataTransfer?.files ?? null))
    }
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('dragleave', onDragLeave)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('dragleave', onDragLeave)
      window.removeEventListener('drop', onDrop)
    }
  })

  const conflict = conflictOf(previews)

  return (
    <section className="panel">
      <h2>{L.files_heading}</h2>
      <p className="lede">{L.files_intro}</p>
      <div
        className={`drop${over ? ' over' : ''}`}
        role="button"
        tabIndex={0}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') input.current?.click() }}
      >
        {busy ? L.files_uploading : L.files_drop}
        <input id="upload-files" ref={input} type="file" multiple hidden onChange={(e) => void send(e.target.files)} />
      </div>
      <div className="actions">
        <button type="button" onClick={() => folder.current?.click()}>{L.files_pick_folder}</button>
        <input id="upload-folder" ref={folder} type="file" multiple hidden
          {...({ webkitdirectory: '' } as Record<string, string>)}
          onChange={(e) => void send(e.target.files)} />
      </div>
      <p className="note">{L.files_formats}</p>
      {skipped > 0 && <div className="alert info">{L.files_skipped(skipped)}</div>}
      {errors.map((message, i) => <div key={i} className="alert error">{message}</div>)}

      {conflict && (
        <div className="alert warn">
          <div>{L.files_conflict(conflict.one.name, conflict.others.map((p) => p.name),
            conflict.temperatures.map((t) => `${t} K`))}</div>
          <div className="actions">
            <button type="button" onClick={() => onRemove(conflict.one.file_id)}>
              {L.files_remove_one(conflict.one.name)}
            </button>
            <button type="button" onClick={() => conflict.others.forEach((p) => onRemove(p.file_id))}>
              {L.files_remove_others(conflict.others.length)}
            </button>
          </div>
        </div>
      )}

      {previews.length > 0 && (
        <>
          <h3>{L.files_listed} ({previews.length})</h3>
          <div className="scroll">
            <table>
              <tbody>
                {previews.map((p) => (
                  <tr key={p.file_id}>
                    <td>{p.name}</td>
                    <td className="num">{p.row_count}</td>
                    <td className="dim">{p.temperatures.length ? L.files_temperatures(p.temperatures) : ''}</td>
                    <td><button onClick={() => onRemove(p.file_id)}>{L.files_remove}</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div className="actions">
        <button className="primary" disabled={previews.length === 0 || conflict !== null} onClick={onNext}>{L.files_next}</button>
        {conflict && <span className="note">{L.files_conflict_block}</span>}
      </div>
    </section>
  )
}
