export function Filters({ filters, onChange }) {
  const set = (key, val) => onChange({ ...filters, [key]: val })
  return (
    <div className="filters">
      <select value={filters.status_filter} onChange={e => set('status_filter', e.target.value)}>
        <option value="">all</option>
        <option value="pending_review">pending</option>
        <option value="approved">approved</option>
        <option value="archived">archived</option>
      </select>
      <select value={filters.category} onChange={e => set('category', e.target.value)}>
        <option value="">all categories</option>
        <option value="code">code</option>
        <option value="project">project</option>
        <option value="personal">personal</option>
        <option value="assistant_chat">assistant chat</option>
      </select>
      <select value={filters.source} onChange={e => set('source', e.target.value)}>
        <option value="">all sources</option>
        <option value="claude_code">claude code</option>
        <option value="copilot">copilot</option>
        <option value="claude_desktop">claude desktop</option>
      </select>
      <input type="search" placeholder="search…" value={filters.q} onChange={e => set('q', e.target.value)} />
    </div>
  )
}
