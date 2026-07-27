import { useCallback, useRef, useState } from 'react'
import {
  streamChat,
  toolStepDetail,
  toolStepLabel,
  type ChatChunk,
  type ThinkingStep,
} from '../api/chat'

type UseChatStreamOptions = {
  machineSerial: string | null
}

type SendMessageOptions = {
  onToken?: (token: string, fullText: string) => void
  onThinkingSteps?: (steps: ThinkingStep[]) => void
}

type UseChatStreamResult = {
  isStreaming: boolean
  error: string | null
  sendMessage: (message: string, options?: SendMessageOptions) => Promise<string>
  abort: () => void
}

let stepCounter = 0

function nextStepId(): string {
  stepCounter += 1
  return `step-${stepCounter}`
}

function applyChunk(steps: ThinkingStep[], chunk: ChatChunk): ThinkingStep[] {
  if (chunk.type === 'step' && chunk.content) {
    const running = steps.map((step) =>
      step.status === 'running' ? { ...step, status: 'done' as const } : step,
    )
    return [
      ...running,
      {
        id: nextStepId(),
        label: chunk.content,
        status: 'running',
      },
    ]
  }

  if (chunk.type === 'tool' && chunk.tool) {
    const detail = toolStepDetail(chunk.tool, chunk.data)
    const label = toolStepLabel(chunk.tool)
    const envelope = chunk.data as { status?: string; message?: string } | undefined
    const isError = envelope?.status === 'error'

    let updated = steps.map((step) =>
      step.status === 'running' ? { ...step, status: 'done' as const } : step,
    )

    const existingIndex = updated.findIndex((step) => step.tool === chunk.tool && step.status === 'done')
    if (existingIndex >= 0) {
      updated = updated.map((step, index) =>
        index === existingIndex
          ? {
              ...step,
              label,
              detail: detail ?? step.detail,
              status: isError ? 'error' : 'done',
            }
          : step,
      )
      return updated
    }

    return [
      ...updated,
      {
        id: nextStepId(),
        label,
        status: isError ? 'error' : 'done',
        tool: chunk.tool,
        detail: isError ? envelope?.message : detail,
      },
    ]
  }

  if (chunk.type === 'error') {
    return steps.map((step) =>
      step.status === 'running' ? { ...step, status: 'error' as const } : step,
    )
  }

  return steps
}

export function useChatStream({ machineSerial }: UseChatStreamOptions): UseChatStreamResult {
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const abort = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsStreaming(false)
  }, [])

  const sendMessage = useCallback(
    async (message: string, options?: SendMessageOptions): Promise<string> => {
      if (!machineSerial) {
        throw new Error('No machine context available for chat.')
      }

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setIsStreaming(true)
      setError(null)

      let assistantText = ''
      let thinkingSteps: ThinkingStep[] = []

      try {
        await streamChat(
          { message, machine_serial: machineSerial },
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
          },
          controller.signal,
        )

        thinkingSteps = thinkingSteps.map((step) =>
          step.status === 'running' ? { ...step, status: 'done' as const } : step,
        )
        options?.onThinkingSteps?.([...thinkingSteps])

        return assistantText.trim()
      } catch (err: unknown) {
        if (controller.signal.aborted) {
          return assistantText.trim()
        }
        const message = err instanceof Error ? err.message : 'Chat stream failed.'
        setError(message)
        throw new Error(message)
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null
        }
        setIsStreaming(false)
      }
    },
    [machineSerial],
  )

  return { isStreaming, error, sendMessage, abort }
}
