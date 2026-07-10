import { useState } from 'react'
import { api } from '../api'

const STATUS_DOT   = { pending_review: 'dot-pending', approved: 'dot-approved', archived: 'dot-archived' }
const STATUS_LABEL = { pending_review: 'pending', approved: 'approved', archived: 'archived' }

export function MemoryCard({ memory, onUpdated, onDeleted }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(memory.content)
  const [busy, setBusy] = useState(false)

  async function patch(body) {
    setBusy(true)
    try {
      const updated = await api.patch(memory.id, body)
      onUpdated(updated)
      setEditing(false)
    } finally { setBusy(false) }
  }

  async function remove() {
    if (!confirm('Delete this memory?')) return
    setBusy(true)
    try { await api.remove(memory.id); onDeleted(memory.id) }
    finally { setBusy(false) }
  }

  const date = new Date(memory.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

  return (
    <div className="card">
      <div className="card-meta">
        <span className={`card-dot ${STATUS_DOT[memory.status]}`} />
        <span>{STATUS_LABEL[memory.status]}</span>
        <span>·</span>
        <span>{memory.source.replace(/_/g, ' ')}</span>
        <span>·</span>
        <span>{memory.category.replace(/_/g, ' ')}</span>
        <span style={{ marginLeft: 'auto' }}>{date}</span>
      </div>

      {editing
        ? <textarea className="card-edit" value={draft} rows={3} onChange={e => setDraft(e.target.value)} />
        : <p className="card-content">{memory.content}</p>
      }

      <div className="card-actions">
        {editing ? (
          <>
            <button className="act act-save" disabled={busy || !draft.trim()} onClick={() => patch({ content: draft.trim() })}>Save</button>
            <button className="act" disabled={busy} onClick={() => { setEditing(false); setDraft(memory.content) }}>Cancel</button>
          </>
        ) : (
          <>
            {memory.status !== 'approved'       && <button className="act act-approve" disabled={busy} onClick={() => patch({ status: 'approved' })}>Approve</button>}
            {memory.status !== 'archived'       && <button className="act" disabled={busy} onClick={() => patch({ status: 'archived' })}>Archive</button>}
            {memory.status !== 'pending_review' && <button className="act" disabled={busy} onClick={() => patch({ status: 'pending_review' })}>Pending</button>}
            <button className="act" disabled={busy} onClick={() => setEditing(true)}>Edit</button>
            <button className="act act-delete" disabled={busy} onClick={remove}>Delete</button>
          </>
        )}
      </div>
    </div>
  )
}
