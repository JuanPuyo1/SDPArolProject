import type { MaintenanceTicket } from '../types/ticket'

type ErrorResponse = {
  error: string
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }

  const csrfToken = getCookie('csrftoken')
  if (csrfToken && options.method && options.method !== 'GET') {
    headers.set('X-CSRFToken', csrfToken)
  }

  const response = await fetch(path, {
    ...options,
    credentials: 'include',
    headers,
  })

  const data = (await response.json().catch(() => ({}))) as T & ErrorResponse

  if (!response.ok) {
    throw new Error(data.error || `Request failed (${response.status})`)
  }

  return data
}

export async function fetchMaintenanceTickets(): Promise<MaintenanceTicket[]> {
  const data = await apiFetch<{ tickets: MaintenanceTicket[] }>(
    '/api/machines/tickets/',
  )
  return data.tickets
}
