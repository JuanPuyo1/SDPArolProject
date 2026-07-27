import { useCallback, useRef, useState } from 'react'
import { streamChat, type ChatChunk } from '../api/chat'

type UseChatStreamOptions = {
  machineSerial: string | null
}

type SendMessageOptions = {
  onToken?: (token: string, fullText: string) => void
}

type UseChatStreamResult = {
  isStreaming: boolean
  error: string | null
  sendMessage: (message: string, options?: SendMessageOptions) => Promise<string>
  abort: () => void
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

      try {
        await streamChat(
          { message, machine_serial: machineSerial },
          {
            onChunk: (chunk: ChatChunk) => {
              if (chunk.type === 'token' && chunk.content) {
                assistantText += chunk.content
                options?.onToken?.(chunk.content, assistantText)
              }
            },
            onError: (message) => setError(message),
          },
          controller.signal,
        )
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
