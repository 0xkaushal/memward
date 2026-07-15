import { useState, useRef, useEffect } from 'react'
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

function CollectionPicker({ memory, collections, onMembershipChange }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (!ref.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  async function toggle(colId) {
    setBusy(true)
    try {
      if (memory.collection_ids.includes(colId)) {
        await api.collections.removeMemory(colId, memory.id)
        onMembershipChange(memory.id, memory.collection_ids.filter(id => id !== colId))
      } else {
        await api.collections.addMemory(colId, memory.id)
        onMembershipChange(memory.id, [...memory.collection_ids, colId])
      }
    } finally { setBusy(false) }
  }

  if (collections.length === 0) return null

  return (
    <div className="col-picker" ref={ref}>
      <button
        className="act act-collections"
        onClick={() => setOpen(v => !v)}
        title="Add to collection"
        disabled={busy}
      >
        ⊞ Collections{memory.collection_ids.length > 0 ? ` (${memory.collection_ids.length})` : ''}
      </button>

      {open && (
        <div className="col-picker-menu">
          <div className="col-picker-title">Add to collection</div>
          {collections.map(col => {
            const isMember = memory.collection_ids.includes(col.id)
            return (
              <button
                key={col.id}
                className={`col-picker-item${isMember ? ' col-picker-item-active' : ''}`}
                onClick={() => toggle(col.id)}
                disabled={busy}
              >
                <span className="col-picker-dot" style={{ background: col.color || 'var(--muted)' }} />
                {col.name}
                {isMember && <span className="col-picker-check">✓</span>}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function MemoryCard({ memory, collections = [], onUpdated, onDeleted, onMembershipChange }) {
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

  // Find collection names this memory belongs to
  const memberCollections = collections.filter(c => memory.collection_ids?.includes(c.id))

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
        {memberCollections.map(c => (
          <span
            key={c.id}
            className="meta-tag meta-tag-collection"
            style={{ '--col-color': c.color || 'var(--muted)' }}
          >
            {c.name}
          </span>
        ))}
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
            <CollectionPicker
              memory={memory}
              collections={collections}
              onMembershipChange={onMembershipChange}
            />
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
