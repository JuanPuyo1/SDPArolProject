export type AuthUser = {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  full_name: string
  is_staff: boolean
  date_joined: string
  last_login: string | null
}

type AuthResponse = {
  user: AuthUser
}

type ErrorResponse = {
  error: string
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
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

export async function ensureCsrfCookie(): Promise<void> {
  await apiFetch('/api/auth/csrf/')
}

export async function fetchCurrentUser(): Promise<AuthUser | null> {
  try {
    await ensureCsrfCookie()
    const data = await apiFetch<AuthResponse>('/api/auth/login/')
    return data.user
  } catch {
    return null
  }
}

export async function login(username: string, password: string): Promise<AuthUser> {
  await ensureCsrfCookie()
  const data = await apiFetch<AuthResponse>('/api/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  return data.user
}

export async function logout(): Promise<void> {
  await apiFetch('/api/auth/logout/', { method: 'POST' })
}

export async function fetchProfile(): Promise<AuthUser> {
  const data = await apiFetch<AuthResponse>('/api/auth/profile/')
  return data.user
}

export async function updateProfile(payload: {
  first_name?: string
  last_name?: string
  email?: string
}): Promise<AuthUser> {
  const data = await apiFetch<AuthResponse>('/api/auth/profile/update/', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
  return data.user
}
