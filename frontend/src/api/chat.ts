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
  session_id?: string
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
  get_quote_history: 'Quote history loaded',
  get_order_status: 'Order status loaded',
  get_contract_info: 'Contract details loaded',
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
    const modelInfo = machine.model as Record<string, unknown> | undefined
    const modelCode = modelInfo?.modelCode ?? machine.model
    if (typeof modelCode === 'string') return modelCode
  }

  if (tool === 'get_quote_history' && Array.isArray(payload.revisions)) {
    return `${payload.revisions.length} revision${payload.revisions.length === 1 ? '' : 's'} found`
  }

  if (tool === 'get_order_status' && Array.isArray(payload.orders)) {
    return `${payload.orders.length} order${payload.orders.length === 1 ? '' : 's'} found`
  }

  if (tool === 'get_contract_info' && Array.isArray(payload.contracts)) {
    return `${payload.contracts.length} contract${payload.contracts.length === 1 ? '' : 's'} found`
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
    onSessionId?: (sessionId: string) => void
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

  const sessionId = response.headers.get('X-Session-Id')
  if (sessionId) {
    handlers.onSessionId?.(sessionId)
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
