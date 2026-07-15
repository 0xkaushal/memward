import { useState } from 'react'
import { api } from '../api'

const STATUS_CONFIG = {
  pending_review: { label: 'Pending',  cls: 'status-pill-pending' },
  approved:       { label: 'Approved', cls: 'status-pill-approved' },
  archived:       { label: 'Archived', cls: 'status-pill-archived' },
}

function fmt(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now - d
  if (diff < 60_000)           return 'just now'
  if (diff < 3_600_000)        return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000)       return `${Math.floor(diff / 3_600_000)}h ago`
  if (diff < 7 * 86_400_000)   return `${Math.floor(diff / 86_400_000)}d ago`
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function MemoryCard({ memory, onUpdated, onDeleted }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft]     = useState(memory.content)
  const [busy, setBusy]       = useState(false)

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

  const { label, cls } = STATUS_CONFIG[memory.status] ?? STATUS_CONFIG.pending_review
  const sourceLabel    = memory.source.replace(/_/g, ' ')
  const categoryLabel  = memory.category.replace(/_/g, ' ')

  return (
    <div className="card">
      {/* Meta row */}
      <div className="card-meta">
        <span className={`status-pill ${cls}`}>
          <span className="status-pill-dot" />
          {label}
        </span>
        <span className="meta-tag">{categoryLabel}</span>
        <span className="meta-tag">{sourceLabel}</span>
        <span className="card-date">{fmt(memory.created_at)}</span>
      </div>

      {/* Content */}
      {editing
        ? <textarea
            className="card-edit"
            value={draft}
            rows={4}
            onChange={e => setDraft(e.target.value)}
            autoFocus
          />
        : <p className="card-content">{memory.content}</p>
      }

      {/* Actions */}
      <div className="card-actions">
        {editing ? (
          <>
            <button className="act act-save" disabled={busy || !draft.trim()} onClick={() => patch({ content: draft.trim() })}>
              Save
            </button>
            <button className="act" disabled={busy} onClick={() => { setEditing(false); setDraft(memory.content) }}>
              Cancel
            </button>
          </>
        ) : (
          <>
            {memory.status !== 'approved' && (
              <button className="act act-approve" disabled={busy} onClick={() => patch({ status: 'approved' })}>
                ✓ Approve
              </button>
            )}
            {memory.status !== 'archived' && (
              <button className="act" disabled={busy} onClick={() => patch({ status: 'archived' })}>
                Archive
              </button>
            )}
            {memory.status !== 'pending_review' && (
              <button className="act" disabled={busy} onClick={() => patch({ status: 'pending_review' })}>
                Mark pending
              </button>
            )}
            <span className="act-separator" />
            <button className="act" disabled={busy} onClick={() => setEditing(true)}>
              Edit
            </button>
            <button className="act act-delete" disabled={busy} onClick={remove}>
              Delete
            </button>
          </>
        )}
      </div>
    </div>
  )
}
