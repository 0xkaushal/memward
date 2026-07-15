const STATUSES = [
  { value: '',               label: 'All',      dot: 'dot-all',      key: '' },
  { value: 'pending_review', label: 'Pending',  dot: 'dot-pending',  key: 'pending_review' },
  { value: 'approved',       label: 'Approved', dot: 'dot-approved', key: 'approved' },
  { value: 'archived',       label: 'Archived', dot: 'dot-archived', key: 'archived' },
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

export function Sidebar({ filters, counts, onChange, onRefresh, loading, onToggleTheme, isDark }) {
  const set = (key, val) => onChange({ ...filters, [key]: val })

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
        </div>

        <div className="sidebar-group">
          <div className="sidebar-group-label">Category</div>
          {CATEGORIES.map(c => (
            <button
              key={c.value}
              className={`sidebar-item${filters.category === c.value ? ' active' : ''}`}
              onClick={() => set('category', c.value)}
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
              className={`sidebar-item${filters.source === s.value ? ' active' : ''}`}
              onClick={() => set('source', s.value)}
            >
              {s.label}
            </button>
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
