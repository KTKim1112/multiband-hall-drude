import { L } from '../labels'

type Props = { checking: boolean; onCheck: () => void }

// FR-108. Shown in place of the steps, because none of them can do anything
// while the program is gone. It names the address this window is holding: the
// program serves on the previous run's address when it can, so a window that
// still cannot reach it is one the reader kept from further back.
export default function OfflineNotice({ checking, onCheck }: Props) {
  const address = typeof window === 'undefined' ? '' : window.location.origin

  return (
    <section className="panel">
      <h2>{L.offline_heading}</h2>
      <div className="alert warn">{L.offline_body(address)}</div>
      <p className="lede">{L.offline_what}</p>
      <p className="note">{L.offline_lost}</p>
      <div className="actions">
        <button type="button" className="primary" onClick={onCheck} disabled={checking}>
          {checking ? L.offline_checking : L.offline_retry}
        </button>
      </div>
    </section>
  )
}
