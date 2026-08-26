const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
const SESSION_KEY = 'citycare_session'

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getStoredSession() {
  try {
    const value = window.localStorage.getItem(SESSION_KEY)
    return value ? JSON.parse(value) : null
  } catch {
    return null
  }
}

export function saveStoredSession(session) {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function clearStoredSession() {
  window.localStorage.removeItem(SESSION_KEY)
}

function errorDetail(payload, fallback) {
  if (typeof payload?.detail === 'string') return payload.detail
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map((item) => item.msg || 'Invalid input').join('; ')
  }
  return fallback
}

async function request(path, { method = 'GET', body, auth = false, signal } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  if (auth) {
    const token = getStoredSession()?.access_token
    if (!token) {
      clearStoredSession()
      throw new ApiError(401, 'Your session has expired. Please sign in again.')
    }
    headers.Authorization = `Bearer ${token}`
  }

  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(0, 'Could not reach CityCare. Check that the clinic server is running.')
  }

  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = errorDetail(payload, 'Something went wrong. Please try again.')
    if (auth && response.status === 401) {
      clearStoredSession()
      window.dispatchEvent(new Event('citycare:unauthorized'))
      if (window.location.pathname !== '/login') window.location.assign('/login')
    }
    throw new ApiError(response.status, detail)
  }
  return payload.data
}

async function upload(path, file, { auth = false } = {}) {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000))
  return request(path, { method: 'POST', auth, body: { filename: file.name, content_base64: btoa(binary) } })
}

export const api = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  upload,
  download: (path) => request(path, { method: 'GET', auth: true }),
}
