const BASE = 'http://127.0.0.1:8000/curation'

async function req(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { 'content-type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 204) return null
  const data = await res.json()
  if (!res.ok) throw new Error(data?.detail ?? res.statusText)
  return data
}

export const api = {
  // Memories
  list:   (params) => req('GET',    `/memories?${new URLSearchParams(params)}`),
  patch:  (id, body) => req('PATCH', `/memories/${id}`, body),
  remove: (id)       => req('DELETE', `/memories/${id}`),

  // Collections
  collections: {
    list:   ()                       => req('GET',    '/collections'),
    create: (name, color)            => req('POST',   '/collections', { name, color }),
    update: (id, body)               => req('PATCH',  `/collections/${id}`, body),
    remove: (id)                     => req('DELETE', `/collections/${id}`),
    addMemory:    (colId, memId)     => req('PUT',    `/collections/${colId}/memories/${memId}`),
    removeMemory: (colId, memId)     => req('DELETE', `/collections/${colId}/memories/${memId}`),
  },
}
