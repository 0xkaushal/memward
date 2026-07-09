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
  list: (params) => req('GET', `/memories?${new URLSearchParams(params)}`),
  patch: (id, body) => req('PATCH', `/memories/${id}`, body),
  remove: (id) => req('DELETE', `/memories/${id}`),
}
