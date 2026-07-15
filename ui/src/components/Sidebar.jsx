import { useState, useRef, useEffect } from 'react'

const STATUSES = [
  { value: '',               label: 'All',      dot: 'dot-all' },
  { value: 'pending_review', label: 'Pending',  dot: 'dot-pending' },
  { value: 'approved',       label: 'Approved', dot: 'dot-approved' },
  { value: 'archived',       label: 'Archived', dot: 'dot-archived' },
]

const CATEGORIES = [
  { value: '',               label: 'All categories' },
  { value: 'code',           label: 'Code' },
  { value: 'project',        label: 'Project' },
  { value: 'personal',       label: 'Personal' },
  { value: 'assistant_chat', label: 'Assistant chat' },
]

const SOURCES = [
  { value: '',               label: 'All sources' },
  { value: 'claude_code',    label: 'Claude Code' },
  { value: 'copilot',        label: 'Copilot' },
  { value: 'claude_desktop', label: 'Claude Desktop' },
]

const COLLECTION_COLORS = [
  '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e',
  '#f97316', '#eab308', '#22c55e', '#14b8a6',
  '#3b82f6', '#a1a1aa',
]

function CollectionItem({ col, active, onClick, onRename, onDelete }) {
  const [menu, setMenu] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [draft, setDraft] = useState(col.name)
  const inputRef = useRef(null)
  const menuRef = useRef(null)

  useEffect(() => {
    if (renaming) inputRef.current?.focus()
  }, [renaming])

  // Close menu on outside click
  useEffect(() => {
    if (!menu) return
    const handler = (e) => {
      if (!menuRef.current?.contains(e.target)) setMenu(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menu])

  function commitRename() {
    const name = draft.trim()
    if (name && name !== col.name) onRename(col.id, name)
    setRenaming(false)
  }

  return (
    <div className={`sidebar-item sidebar-col-item${active ? ' active' : ''}`}>
      <button
        className="sidebar-col-btn"
        onClick={onClick}
        title={col.name}
      >
        <span className="sidebar-col-dot" style={{ background: col.color || 'var(--muted)' }} />
        {renaming
          ? <input
              ref={inputRef}
              className="sidebar-col-rename"
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onBlur={commitRename}
              onKeyDown={e => {
                if (e.key === 'Enter') commitRename()
                if (e.key === 'Escape') { setRenaming(false); setDraft(col.name) }
              }}
              onClick={e => e.stopPropagation()}
            />
          : <span className="sidebar-col-name">{col.name}</span>
        }
        {col.memory_count > 0 && !renaming && (
          <span className="sidebar-count">{col.memory_count}</span>
        )}
      </button>

      <div className="sidebar-col-more" ref={menuRef}>
        <button
          className="sidebar-col-more-btn"
          title="More"
          onClick={e => { e.stopPropagation(); setMenu(v => !v) }}
        >⋯</button>

        {menu && (
          <div className="col-menu">
            <button className="col-menu-item" onClick={() => { setMenu(false); setRenaming(true); setDraft(col.name) }}>
              Rename
            </button>
            <button className="col-menu-item col-menu-danger" onClick={() => { setMenu(false); onDelete(col.id) }}>
              Delete
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function NewCollectionForm({ onConfirm, onCancel }) {
  const [name, setName] = useState('')
  const [color, setColor] = useState(COLLECTION_COLORS[0])
  const inputRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  function submit(e) {
    e.preventDefault()
    if (!name.trim()) return
    onConfirm(name.trim(), color)
  }

  return (
    <form className="new-col-form" onSubmit={submit}>
      <div className="new-col-colors">
        {COLLECTION_COLORS.map(c => (
          <button
            key={c}
            type="button"
            className={`new-col-swatch${color === c ? ' selected' : ''}`}
            style={{ background: c }}
            onClick={() => setColor(c)}
          />
        ))}
      </div>
      <input
        ref={inputRef}
        className="new-col-input"
        placeholder="Collection name…"
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={e => e.key === 'Escape' && onCancel()}
      />
      <div className="new-col-actions">
        <button type="submit" className="new-col-btn-primary" disabled={!name.trim()}>Create</button>
        <button type="button" className="new-col-btn-cancel" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

export function Sidebar({
  filters, counts, onChange, onRefresh, loading, onToggleTheme, isDark,
  collections, onCreateCollection, onRenameCollection, onDeleteCollection,
}) {
  const [creatingCol, setCreatingCol] = useState(false)
  const set = (key, val) => onChange({ ...filters, [key]: val })

  function selectCollection(colId) {
    onChange({ ...filters, collection_id: colId, status_filter: '', category: '', source: '' })
  }

  function clearCollection() {
    onChange({ ...filters, collection_id: '' })
  }

  return (
    <aside className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <span className="sidebar-logo-dot" />
          memward
        </div>
      </div>

      {/* Search */}
      <div className="sidebar-search-wrap">
        <input
          className="sidebar-search"
          type="search"
          placeholder="Search memories…"
          value={filters.q}
          onChange={e => set('q', e.target.value)}
        />
      </div>

      {/* Nav groups */}
      <nav className="sidebar-nav">
        <div className="sidebar-group">
          <div className="sidebar-group-label">Status</div>
          {STATUSES.map(s => (
            <button
              key={s.value}
              className={`sidebar-item${!filters.collection_id && filters.status_filter === s.value ? ' active' : ''}`}
              onClick={() => { clearCollection(); set('status_filter', s.value) }}
            >
              <span className={`sidebar-dot ${s.dot}`} />
              {s.label}
              {counts.status?.[s.value] != null && (
                <span className="sidebar-count">{counts.status[s.value]}</span>
              )}
            </button>
          ))}
        </div>

        <div className="sidebar-group">
          <div className="sidebar-group-label">Category</div>
          {CATEGORIES.map(c => (
            <button
              key={c.value}
              className={`sidebar-item${!filters.collection_id && filters.category === c.value ? ' active' : ''}`}
              onClick={() => { clearCollection(); set('category', c.value) }}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className="sidebar-group">
          <div className="sidebar-group-label">Source</div>
          {SOURCES.map(s => (
            <button
              key={s.value}
              className={`sidebar-item${!filters.collection_id && filters.source === s.value ? ' active' : ''}`}
              onClick={() => { clearCollection(); set('source', s.value) }}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Collections */}
        <div className="sidebar-group">
          <div className="sidebar-group-label sidebar-group-label-row">
            Collections
            <button
              className="sidebar-add-col-btn"
              title="New collection"
              onClick={() => setCreatingCol(true)}
            >+</button>
          </div>

          {creatingCol && (
            <NewCollectionForm
              onConfirm={(name, color) => { onCreateCollection(name, color); setCreatingCol(false) }}
              onCancel={() => setCreatingCol(false)}
            />
          )}

          {collections.length === 0 && !creatingCol && (
            <div className="sidebar-col-empty">No collections yet</div>
          )}

          {collections.map(col => (
            <CollectionItem
              key={col.id}
              col={col}
              active={filters.collection_id === col.id}
              onClick={() => selectCollection(col.id)}
              onRename={onRenameCollection}
              onDelete={onDeleteCollection}
            />
          ))}
        </div>
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <button
          className="btn-icon"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh"
          style={{ marginRight: 'auto' }}
        >
          {loading ? '·' : '↺'}&nbsp;Refresh
        </button>
        <button className="btn-icon" onClick={onToggleTheme} title="Toggle theme">
          {isDark ? '☀' : '☾'}
        </button>
      </div>
    </aside>
  )
}
