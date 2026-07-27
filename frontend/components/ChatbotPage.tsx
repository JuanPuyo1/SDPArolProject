import { useEffect, useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'
import ChatMessage from './ChatMessage'
import type { ChatAttachment, ChatMessageData } from './ChatMessage'
import { useAuth } from '../src/hooks/useAuth'
import { useDefaultMachine } from '../src/hooks/useMachine'
import { useChatStream } from '../src/hooks/useChat'
import './ChatbotPage.css'

const ACCEPTED_TYPES = 'image/*,.txt,.text/plain,.pdf,application/pdf'

function isImage(file: File) {
  return file.type.startsWith('image/')
}

function buildWelcomeMessage(model: string, serial: string): ChatMessageData {
  return {
    id: 'welcome',
    role: 'assistant',
    text: `Hi, I'm the Arol Troubleshooting & Service assistant for the ${model} (${serial}). Ask about alarms, error codes, or maintenance — I'll call MCP tools, show each step, and stream a reply.`,
    attachments: [],
  }
}

export default function ChatbotPage() {
  const { user } = useAuth()
  const { machine, loading: machineLoading, error: machineError } = useDefaultMachine()
  const serial = machine?.serialNumber ?? null
  const modelLabel = machine?.model ?? machine?.fullModel ?? 'your machine'

  const { isStreaming, error: chatError, sendMessage } = useChatStream({
    machineSerial: serial,
  })

  const [messages, setMessages] = useState<ChatMessageData[]>([])
  const [draftText, setDraftText] = useState('')
  const [draftAttachments, setDraftAttachments] = useState<ChatAttachment[]>([])
  const welcomeSerialRef = useRef<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!serial) return
    if (welcomeSerialRef.current === serial) return
    welcomeSerialRef.current = serial
    setMessages([buildWelcomeMessage(modelLabel, serial)])
  }, [serial, modelLabel])

  function handleFilesSelected(fileList: FileList | null) {
    if (!fileList) return
    const newAttachments: ChatAttachment[] = Array.from(fileList).map((file) => ({
      id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
      file,
      previewUrl: isImage(file) ? URL.createObjectURL(file) : null,
    }))
    setDraftAttachments((prev) => [...prev, ...newAttachments])
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function removeDraftAttachment(id: string) {
    setDraftAttachments((prev) => {
      const target = prev.find((att) => att.id === id)
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl)
      return prev.filter((att) => att.id !== id)
    })
  }

  async function handleSubmit(event: SyntheticEvent) {
    event.preventDefault()
    if (!draftText.trim() && draftAttachments.length === 0) return
    if (!serial || isStreaming) return

    const userText = draftText.trim()
    const userMessage: ChatMessageData = {
      id: `msg-${Date.now()}`,
      role: 'user',
      text: userText,
      attachments: draftAttachments,
    }

    const assistantId = `reply-${Date.now()}`
    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantId, role: 'assistant', text: '', attachments: [], thinkingSteps: [] },
    ])
    setDraftText('')
    setDraftAttachments([])

    const prompt =
      userText ||
      (userMessage.attachments.length > 0
        ? `Please review my attachment: ${userMessage.attachments.map((a) => a.file.name).join(', ')}`
        : '')

    try {
      const reply = await sendMessage(prompt, {
        onToken: (_token, fullText) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, text: fullText } : m)),
          )
        },
        onThinkingSteps: (steps) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, thinkingSteps: steps } : m)),
          )
        },
      })
      if (!reply) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, text: 'No response received from the orchestrator.' }
              : m,
          ),
        )
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Chat request failed.'
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, text: message } : m)),
      )
    }
  }

  const disabled = machineLoading || !serial || isStreaming
  const statusError = machineError || chatError

  return (
    <div className="chatbot-page">
      <div className="chatbot-page__header">
        <h1>AI Chatbot</h1>
        <p>
          Troubleshooting &amp; Service agent
          {serial ? (
            <>
              {' '}
              for {modelLabel} &middot; Serial {serial}
            </>
          ) : machineLoading ? (
            ' — loading machine context…'
          ) : (
            ' — no machine assigned to your account'
          )}
          {user ? <> &middot; {user.username}</> : null}
        </p>
        {statusError && <p className="chatbot-page__error">{statusError}</p>}
      </div>

      <div className="chatbot-page__messages">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
      </div>

      <form className="chatbot-page__composer" onSubmit={handleSubmit}>
        {draftAttachments.length > 0 && (
          <div className="chatbot-page__draft-attachments">
            {draftAttachments.map((att) => (
              <div key={att.id} className="draft-attachment">
                {att.previewUrl ? (
                  <img src={att.previewUrl} alt={att.file.name} />
                ) : (
                  <span className="draft-attachment__ext">
                    {att.file.name.split('.').pop()?.toUpperCase()}
                  </span>
                )}
                <span className="draft-attachment__name">{att.file.name}</span>
                <button
                  type="button"
                  className="draft-attachment__remove"
                  onClick={() => removeDraftAttachment(att.id)}
                  aria-label={`Remove ${att.file.name}`}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="chatbot-page__input-row">
          <button
            type="button"
            className="attach-btn"
            onClick={() => fileInputRef.current?.click()}
            aria-label="Attach a file"
            title="Attach image, .txt or .pdf"
            disabled={disabled}
          >
            📎
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            multiple
            hidden
            onChange={(e) => handleFilesSelected(e.target.files)}
          />
          <textarea
            className="chatbot-page__textarea"
            placeholder={
              serial
                ? 'Ask about setup, maintenance or troubleshooting…'
                : 'Assign a machine to your account to start chatting.'
            }
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void handleSubmit(e)
              }
            }}
            rows={1}
            disabled={disabled}
          />
          <button type="submit" className="btn btn--primary" disabled={disabled}>
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
