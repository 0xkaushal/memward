import { useState, useEffect, useCallback, useMemo } from 'react'
import { api } from './api'
import { Sidebar } from './components/Sidebar'
import { MemoryCard } from './components/MemoryCard'
import './App.css'

const DEFAULT_FILTERS = { status_filter: '', category: '', source: '', q: '', collection_id: '' }

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
  const [memories, setMemories]       = useState([])
  const [collections, setCollections] = useState([])
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)
  const [filters, setFilters]         = useState(DEFAULT_FILTERS)
  const { toggle, isDark }            = useTheme()

  // Load memories (respects status/category/source filters; collection filtering is client-side)
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

  // Load collections once on mount and after mutations
  const loadCollections = useCallback(async () => {
    try {
      const data = await api.collections.list()
      setCollections(data.results)
    } catch (_) {}
  }, [])

  useEffect(() => { loadCollections() }, [loadCollections])

  // Client-side filter: text search + collection membership
  const visible = useMemo(() => {
    let result = memories
    if (filters.collection_id) {
      result = result.filter(m => m.collection_ids?.includes(filters.collection_id))
    }
    if (filters.q.trim()) {
      const q = filters.q.toLowerCase()
      result = result.filter(m => m.content.toLowerCase().includes(q))
    }
    return result
  }, [memories, filters.q, filters.collection_id])

  const counts = useMemo(() => {
    const status = { '': memories.length }
    memories.forEach(m => { status[m.status] = (status[m.status] || 0) + 1 })
    return { status }
  }, [memories])

  // Derive title
  const title = useMemo(() => {
    if (filters.collection_id) {
      const col = collections.find(c => c.id === filters.collection_id)
      return col ? col.name : 'Collection'
    }
    if (filters.status_filter) return filters.status_filter.replace('_', ' ')
    if (filters.category)      return filters.category.replace(/_/g, ' ')
    if (filters.source)        return filters.source.replace(/_/g, ' ')
    return 'All memories'
  }, [filters, collections])

  // Collection mutations
  async function handleCreateCollection(name, color) {
    await api.collections.create(name, color)
    loadCollections()
  }

  async function handleRenameCollection(id, name) {
    await api.collections.update(id, { name })
    loadCollections()
  }

  async function handleDeleteCollection(id) {
    if (!confirm('Delete this collection? Memories will not be deleted.')) return
    await api.collections.remove(id)
    // If viewing the deleted collection, reset
    if (filters.collection_id === id) setFilters(f => ({ ...f, collection_id: '' }))
    loadCollections()
  }

  // When a memory's collection membership changes, update local state
  function handleMembershipChange(memoryId, newCollectionIds) {
    setMemories(prev => prev.map(m => m.id === memoryId ? { ...m, collection_ids: newCollectionIds } : m))
    loadCollections()  // refresh counts
  }

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
        collections={collections}
        onCreateCollection={handleCreateCollection}
        onRenameCollection={handleRenameCollection}
        onDeleteCollection={handleDeleteCollection}
      />

      <div className="pane">
        <div className="pane-header">
          {filters.collection_id && (
            <span
              className="pane-col-dot"
              style={{
                background: collections.find(c => c.id === filters.collection_id)?.color || 'var(--muted)'
              }}
            />
          )}
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
                  <div>
                    {filters.q
                      ? `No results for "${filters.q}"`
                      : filters.collection_id
                        ? 'No memories in this collection yet'
                        : 'No memories yet'}
                  </div>
                </div>
              </div>
            )
            : (
              <div className="list">
                {visible.map(m => (
                  <MemoryCard
                    key={m.id}
                    memory={m}
                    collections={collections}
                    onUpdated={u => setMemories(prev => prev.map(x => x.id === u.id ? { ...u, collection_ids: x.collection_ids } : x))}
                    onDeleted={id => setMemories(prev => prev.filter(x => x.id !== id))}
                    onMembershipChange={handleMembershipChange}
                  />
                ))}
              </div>
            )
        }
      </div>
    </div>
  )
}
