import { useState, useEffect, useCallback } from 'react'
import { api } from './api'
import { Filters } from './components/Filters'
import { MemoryCard } from './components/MemoryCard'
import './App.css'

const DEFAULT_FILTERS = { status_filter: '', category: '', source: '', q: '' }

export default function App() {
  const [memories, setMemories] = useState([])
  const [total, setTotal] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState(DEFAULT_FILTERS)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit: 200 }
      if (filters.status_filter) params.status_filter = filters.status_filter
      if (filters.category)      params.category       = filters.category
      if (filters.source)        params.source         = filters.source
      const data = await api.list(params)
      setTotal(data.total)
      setMemories(data.results)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [filters.status_filter, filters.category, filters.source])

  useEffect(() => { load() }, [load])

  const visible = filters.q.trim()
    ? memories.filter(m => m.content.toLowerCase().includes(filters.q.toLowerCase()))
    : memories

  function handleUpdated(updated) {
    setMemories(prev => prev.map(m => m.id === updated.id ? updated : m))
  }

  function handleDeleted(id) {
    setMemories(prev => prev.filter(m => m.id !== id))
    setTotal(t => t - 1)
  }

  return (
    <>
      <header className="header">
        <div className="header-left">
          <h1>memward</h1>
          <span className="header-sub">memory curation</span>
        </div>
        <div className="header-right">
          {total !== null && <span className="total-badge">{total} memories</span>}
          <button className="btn btn-refresh" onClick={load} disabled={loading}>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </header>

      <Filters filters={filters} onChange={setFilters} />

      <main className="main">
        {error && <div className="error-banner">Error: {error}</div>}

        {!loading && visible.length === 0 && !error && (
          <div className="empty">No memories found.</div>
        )}

        {visible.map(m => (
          <MemoryCard
            key={m.id}
            memory={m}
            onUpdated={handleUpdated}
            onDeleted={handleDeleted}
          />
        ))}
      </main>
    </>
  )
}
