export type ChatChunkType = 'token' | 'tool' | 'done' | 'error'

export type ChatChunk = {
  type: ChatChunkType
  content?: string
  tool?: string
  data?: unknown
  message?: string
}

export type ChatRequest = {
  message: string
  machine_serial?: string
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

function parseSseBlock(block: string): ChatChunk | null {
  const dataLine = block
    .split('\n')
    .map((line) => line.trim())
    .find((line) => line.startsWith('data:'))
  if (!dataLine) return null

  const jsonText = dataLine.slice('data:'.length).trim()
  if (!jsonText) return null

  try {
    return JSON.parse(jsonText) as ChatChunk
  } catch {
    return null
  }
}

export async function streamChat(
  payload: ChatRequest,
  handlers: {
    onChunk: (chunk: ChatChunk) => void
    onError?: (message: string) => void
  },
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const csrfToken = getCookie('csrftoken')
  if (csrfToken) {
    headers.set('X-CSRFToken', csrfToken)
  }

  const response = await fetch('/api/agents/chat/', {
    method: 'POST',
    credentials: 'include',
    headers,
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as { error?: string }
    throw new Error(data.error || `Chat request failed (${response.status})`)
  }

  if (!response.body) {
    throw new Error('Chat response had no body.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''

    for (const part of parts) {
      const chunk = parseSseBlock(part)
      if (!chunk) continue

      handlers.onChunk(chunk)
      if (chunk.type === 'error' && chunk.message) {
        handlers.onError?.(chunk.message)
      }
      if (chunk.type === 'done' || chunk.type === 'error') {
        return
      }
    }
  }
}
