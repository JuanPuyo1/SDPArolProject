export type ChatChunkType = 'token' | 'tool' | 'step' | 'done' | 'error'

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

export type ThinkingStepStatus = 'running' | 'done' | 'error'

export type ThinkingStep = {
  id: string
  label: string
  status: ThinkingStepStatus
  tool?: string
  detail?: string
}

const TOOL_LABELS: Record<string, string> = {
  get_machine_info: 'Machine context loaded',
  search_error_codes: 'Error code lookup complete',
  search_manual: 'Manual search complete',
  query_telemetry: 'Telemetry query complete',
  create_ticket: 'Support ticket created',
  list_spare_parts: 'Spare parts lookup complete',
}

export function toolStepLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? `${tool} complete`
}

export function toolStepDetail(tool: string, data: unknown): string | undefined {
  if (!data || typeof data !== 'object') return undefined
  const envelope = data as { status?: string; data?: Record<string, unknown>; message?: string }

  if (envelope.status === 'error') {
    return envelope.message
  }

  const payload = envelope.data
  if (!payload) return undefined

  if (tool === 'create_ticket' && typeof payload.ticket_id === 'string') {
    return `Ticket ${payload.ticket_id} · ${payload.priority ?? 'medium'} priority`
  }

  if (tool === 'search_error_codes' && Array.isArray(payload.hits)) {
    const codes = payload.hits
      .map((hit) => (typeof hit === 'object' && hit && 'code' in hit ? String(hit.code) : null))
      .filter(Boolean)
    if (codes.length) return `Matched: ${codes.join(', ')}`
  }

  if (tool === 'get_machine_info' && payload.machine && typeof payload.machine === 'object') {
    const machine = payload.machine as Record<string, unknown>
    const identification = machine.identification as Record<string, unknown> | undefined
    const model = identification?.model ?? machine.model
    if (typeof model === 'string') return model
  }

  return undefined
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
