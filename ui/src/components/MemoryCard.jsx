import { useState } from 'react'
import { api } from '../api'
import { StatusBadge, Badge } from './Badge'

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
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!confirm(`Delete this memory?\n\n"${memory.content.slice(0, 120)}"`)) return
    setBusy(true)
    try {
      await api.remove(memory.id)
      onDeleted(memory.id)
    } finally {
      setBusy(false)
    }
  }

  const date = new Date(memory.created_at).toLocaleString()

  return (
    <div className="card">
      <div className="card-top">
        <StatusBadge status={memory.status} />
        <Badge className="badge-source">{memory.source.replace(/_/g, ' ')}</Badge>
        <Badge className="badge-category">{memory.category.replace(/_/g, ' ')}</Badge>
        <span className="card-date">{date}</span>
      </div>

      {editing ? (
        <textarea
          className="card-edit"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          rows={4}
        />
      ) : (
        <p className="card-content">{memory.content}</p>
      )}

      <div className="card-actions">
        {editing ? (
          <>
            <button
              className="btn btn-save"
              disabled={busy || !draft.trim()}
              onClick={() => patch({ content: draft.trim() })}
            >Save</button>
            <button className="btn btn-cancel" disabled={busy} onClick={() => { setEditing(false); setDraft(memory.content) }}>Cancel</button>
          </>
        ) : (
          <>
            {memory.status !== 'approved'       && <button className="btn btn-approve"  disabled={busy} onClick={() => patch({ status: 'approved' })}>Approve</button>}
            {memory.status !== 'archived'       && <button className="btn btn-archive"  disabled={busy} onClick={() => patch({ status: 'archived' })}>Archive</button>}
            {memory.status !== 'pending_review' && <button className="btn btn-pending"  disabled={busy} onClick={() => patch({ status: 'pending_review' })}>Mark pending</button>}
            <button className="btn btn-edit"   disabled={busy} onClick={() => setEditing(true)}>Edit</button>
            <button className="btn btn-delete" disabled={busy} onClick={remove}>Delete</button>
          </>
        )}
      </div>
    </div>
  )
}
