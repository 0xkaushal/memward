const STATUSES = [
  { value: '', label: 'All memories',    dot: 'dot-all' },
  { value: 'pending_review', label: 'Pending',  dot: 'dot-pending' },
  { value: 'approved',       label: 'Approved', dot: 'dot-approved' },
  { value: 'archived',       label: 'Archived', dot: 'dot-archived' },
]

const CATEGORIES = [
  { value: '', label: 'All categories' },
  { value: 'code',           label: 'Code' },
  { value: 'project',        label: 'Project' },
  { value: 'personal',       label: 'Personal' },
  { value: 'assistant_chat', label: 'Assistant chat' },
]

const SOURCES = [
  { value: '', label: 'All sources' },
  { value: 'claude_code',    label: 'Claude Code' },
  { value: 'copilot',        label: 'Copilot' },
  { value: 'claude_desktop', label: 'Claude Desktop' },
]

export function Sidebar({ filters, counts, onChange, onRefresh, loading, onToggleTheme, isDark }) {
  const set = (key, val) => onChange({ ...filters, [key]: val })

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">memward</div>

      <input
        className="sidebar-search"
        type="search"
        placeholder="Search…"
        value={filters.q}
        onChange={e => set('q', e.target.value)}
      />

      <div className="sidebar-section">Status</div>
      {STATUSES.map(s => (
        <button
          key={s.value}
          className={`sidebar-item${filters.status_filter === s.value ? ' active' : ''}`}
          onClick={() => set('status_filter', s.value)}
        >
          <span className={`sidebar-dot ${s.dot}`} />
          {s.label}
          {counts.status?.[s.value] != null && (
            <span className="sidebar-count">{counts.status[s.value]}</span>
          )}
        </button>
      ))}

      <div className="sidebar-section" style={{ marginTop: '.5rem' }}>Category</div>
      {CATEGORIES.map(c => (
        <button
          key={c.value}
          className={`sidebar-item${filters.category === c.value ? ' active' : ''}`}
          onClick={() => set('category', c.value)}
        >
          {c.label}
        </button>
      ))}

      <div className="sidebar-section" style={{ marginTop: '.5rem' }}>Source</div>
      {SOURCES.map(s => (
        <button
          key={s.value}
          className={`sidebar-item${filters.source === s.value ? ' active' : ''}`}
          onClick={() => set('source', s.value)}
        >
          {s.label}
        </button>
      ))}

      <div className="sidebar-bottom">
        <button className="btn-icon" onClick={onRefresh} disabled={loading} title="Refresh">
          {loading ? '…' : '↺'}
        </button>
        <button className="btn-icon" onClick={onToggleTheme} title="Toggle theme">
          {isDark ? '☀' : '☾'}
        </button>
      </div>
    </aside>
  )
}
