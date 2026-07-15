import { useState, useEffect, useCallback, useMemo } from 'react'
import { api } from './api'
import { Sidebar } from './components/Sidebar'
import { MemoryCard } from './components/MemoryCard'
import './App.css'

const DEFAULT_FILTERS = { status_filter: '', category: '', source: '', q: '' }

function useTheme() {
  const systemDark = () => window.matchMedia('(prefers-color-scheme: dark)').matches
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'system')
  useEffect(() => {
    const resolved = theme === 'system' ? (systemDark() ? 'dark' : 'light') : theme
    document.documentElement.setAttribute('data-theme', resolved)
    localStorage.setItem('theme', theme)
  }, [theme])
  const toggle = () => setTheme(t =>
    t === 'system' ? (systemDark() ? 'light' : 'dark') : (t === 'dark' ? 'light' : 'dark')
  )
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  return { toggle, isDark }
}

function SkeletonList() {
  return (
    <div className="list">
      {[100, 80, 120, 90, 110].map((w, i) => (
        <div key={i} className="skeleton skeleton-card" style={{ height: `${w}px` }} />
      ))}
    </div>
  )
}

export default function App() {
  const [memories, setMemories] = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [filters, setFilters]   = useState(DEFAULT_FILTERS)
  const { toggle, isDark }      = useTheme()

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const params = { limit: 200 }
      if (filters.status_filter) params.status_filter = filters.status_filter
      if (filters.category)      params.category       = filters.category
      if (filters.source)        params.source         = filters.source
      const data = await api.list(params)
      setMemories(data.results)
    } catch (e) { setError(e.message) }
    finally     { setLoading(false) }
  }, [filters.status_filter, filters.category, filters.source])

  useEffect(() => { load() }, [load])

  const visible = useMemo(() =>
    filters.q.trim()
      ? memories.filter(m => m.content.toLowerCase().includes(filters.q.toLowerCase()))
      : memories,
    [memories, filters.q]
  )

  const counts = useMemo(() => {
    const status = { '': memories.length }
    memories.forEach(m => { status[m.status] = (status[m.status] || 0) + 1 })
    return { status }
  }, [memories])

  const title = filters.status_filter
    ? filters.status_filter.replace('_', ' ')
    : filters.category
      ? filters.category.replace(/_/g, ' ')
      : filters.source
        ? filters.source.replace(/_/g, ' ')
        : 'All memories'

  return (
    <div className="layout">
      <Sidebar
        filters={filters}
        counts={counts}
        onChange={setFilters}
        onRefresh={load}
        loading={loading}
        onToggleTheme={toggle}
        isDark={isDark}
      />

      <div className="pane">
        <div className="pane-header">
          <span className="pane-title">{title}</span>
          {!loading && <span className="pane-count">{visible.length}</span>}
        </div>

        {error && <div className="error-banner">{error}</div>}

        {loading
          ? <SkeletonList />
          : !error && visible.length === 0
            ? (
              <div className="list">
                <div className="empty">
                  <div className="empty-icon">◎</div>
                  <div>{filters.q ? `No results for "${filters.q}"` : 'No memories yet'}</div>
                </div>
              </div>
            )
            : (
              <div className="list">
                {visible.map(m => (
                  <MemoryCard key={m.id} memory={m}
                    onUpdated={u => setMemories(prev => prev.map(x => x.id === u.id ? u : x))}
                    onDeleted={id => setMemories(prev => prev.filter(x => x.id !== id))}
                  />
                ))}
              </div>
            )
        }
      </div>
    </div>
  )
}
