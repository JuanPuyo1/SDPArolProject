import { useCallback, useRef, useState } from 'react'
import {
  streamFleetChat,
  toolStepDetail,
  toolStepLabel,
  type ChatChunk,
  type ThinkingStep,
} from '../api/fleetChat'

type SendMessageOptions = {
  onToken?: (token: string, fullText: string) => void
  onThinkingSteps?: (steps: ThinkingStep[]) => void
}

type UseFleetChatStreamOptions = {
  // Fired whenever the hook learns the session id it's using (every turn
  // echoes/mints one) -- lets the caller persist it (see fleetChatStorage.ts).
  onSessionIdChange?: (sessionId: string) => void
}

type UseFleetChatStreamResult = {
  isStreaming: boolean
  error: string | null
  sendMessage: (message: string, options?: SendMessageOptions) => Promise<string>
  abort: () => void
  resetConversation: () => void
  resumeSessionId: (sessionId: string | null) => void
}

let stepCounter = 0

function nextStepId(): string {
  stepCounter += 1
  return `fleet-step-${stepCounter}`
}

function settleRunning(
  steps: ThinkingStep[],
  status: 'done' | 'error',
  now: number,
): ThinkingStep[] {
  return steps.map((step) =>
    step.status === 'running'
      ? { ...step, status, durationMs: step.startedAt ? now - step.startedAt : undefined }
      : step,
  )
}

function applyChunk(steps: ThinkingStep[], chunk: ChatChunk): ThinkingStep[] {
  const now = Date.now()

  if (chunk.type === 'step' && chunk.content) {
    return [
      ...settleRunning(steps, 'done', now),
      { id: nextStepId(), label: chunk.content, status: 'running', startedAt: now },
    ]
  }

  if (chunk.type === 'tool' && chunk.tool) {
    const detail = toolStepDetail(chunk.tool, chunk.data)
    const label = toolStepLabel(chunk.tool)
    const envelope = chunk.data as { status?: string; message?: string } | undefined
    const isError = envelope?.status === 'error'
    const resolvedStatus = isError ? ('error' as const) : ('done' as const)

    const updated = settleRunning(steps, resolvedStatus, now)
    const existingIndex = updated.findIndex((step) => step.tool === chunk.tool && step.status === resolvedStatus)
    if (existingIndex >= 0) {
      return updated.map((step, index) =>
        index === existingIndex
          ? { ...step, label, detail: detail ?? step.detail, status: resolvedStatus }
          : step,
      )
    }

    return [
      ...updated,
      {
        id: nextStepId(),
        label,
        status: resolvedStatus,
        tool: chunk.tool,
        detail: isError ? envelope?.message : detail,
      },
    ]
  }

  if (chunk.type === 'error') {
    return settleRunning(steps, 'error', now)
  }

  return steps
}

/** Fleet-wide-chatbot counterpart to useChatStream (see useChat.ts) --
 * same streaming/thinking-step machinery, minus the machineSerial
 * requirement and per-agent attribution (this chatbot has no router). */
export function useFleetChatStream({
  onSessionIdChange,
}: UseFleetChatStreamOptions = {}): UseFleetChatStreamResult {
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const sessionIdRef = useRef<string | null>(null)

  const abort = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsStreaming(false)
  }, [])

  const resetConversation = useCallback(() => {
    sessionIdRef.current = null
  }, [])

  const resumeSessionId = useCallback((sessionId: string | null) => {
    sessionIdRef.current = sessionId
  }, [])

  const sendMessage = useCallback(
    async (message: string, options?: SendMessageOptions): Promise<string> => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setIsStreaming(true)
      setError(null)

      let assistantText = ''
      let thinkingSteps: ThinkingStep[] = []

      try {
        await streamFleetChat(
          { message, session_id: sessionIdRef.current ?? undefined },
          {
            onChunk: (chunk: ChatChunk) => {
              if (chunk.type === 'token' && chunk.content) {
                assistantText += chunk.content
                options?.onToken?.(chunk.content, assistantText)
              }

              if (chunk.type === 'step' || chunk.type === 'tool' || chunk.type === 'error') {
                thinkingSteps = applyChunk(thinkingSteps, chunk)
                options?.onThinkingSteps?.([...thinkingSteps])
              }
            },
            onError: (message) => setError(message),
            onSessionId: (sessionId) => {
              sessionIdRef.current = sessionId
              onSessionIdChange?.(sessionId)
            },
          },
          controller.signal,
        )

        thinkingSteps = settleRunning(thinkingSteps, 'done', Date.now())
        options?.onThinkingSteps?.([...thinkingSteps])

        return assistantText.trim()
      } catch (err: unknown) {
        if (controller.signal.aborted) {
          return assistantText.trim()
        }
        const message = err instanceof Error ? err.message : 'Fleet chat stream failed.'
        setError(message)
        throw new Error(message, { cause: err })
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null
        }
        setIsStreaming(false)
      }
    },
    [onSessionIdChange],
  )

  return { isStreaming, error, sendMessage, abort, resetConversation, resumeSessionId }
}
