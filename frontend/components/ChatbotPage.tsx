import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'
import ChatMessage from './ChatMessage'
import type { ChatAttachment, ChatMessageData } from './ChatMessage'
import { useAuth } from '../src/hooks/useAuth'
import { useDefaultMachine } from '../src/hooks/useMachine'
import { useChatStream } from '../src/hooks/useChat'
import { AGENT_TABS, type AgentTabId } from '../src/api/chat'
import { loadPersistedChat, savePersistedChat } from '../src/api/chatStorage'
// @ts-expect-error Side-effect CSS import resolved by bundler
import './ChatbotPage.css'

const ACCEPTED_TYPES = 'image/*,.txt,.text/plain,.pdf,application/pdf'

function isImage(file: File) {
  return file.type.startsWith('image/')
}

function buildWelcomeMessage(model: string, serial: string): ChatMessageData {
  return {
    id: 'welcome',
    role: 'assistant',
    text: `Hi, I'm the Arol Chatbot assistant for the ${model} (${serial}). Ask about anything related to the machine, the telemetry, orders and/or services — I'll be happy to help you`,
    attachments: [],
  }
}

/** File/ObjectURL references in ChatAttachment aren't JSON-serializable and
 * don't survive a reload anyway (the blob URL dies with the document) --
 * drop them before persisting, keep everything else. */
function stripAttachmentsForStorage(messages: ChatMessageData[]): ChatMessageData[] {
  return messages.map((m) => (m.attachments.length ? { ...m, attachments: [] } : m))
}

export default function ChatbotPage() {
  const { user } = useAuth()
  const { machine, loading: machineLoading, error: machineError } = useDefaultMachine()
  const serial = machine?.serialNumber ?? null
  const modelLabel = machine?.model.modelCode ?? 'your machine'

  // Mirrors the session id the hook is currently using -- the hook itself
  // only tracks it imperatively (a ref, not state), so this is needed here
  // to read it from persistChat() below.
  const chatSessionIdRef = useRef<string | null>(null)

  const [messages, setMessages] = useState<ChatMessageData[]>([])
  const [draftText, setDraftText] = useState('')
  const [draftAttachments, setDraftAttachments] = useState<ChatAttachment[]>([])
  const [activeTab, setActiveTab] = useState<AgentTabId>('all')
  const restoredKeyRef = useRef<string | null>(null)
  // Mirrors `messages`, but updated synchronously (not via a useEffect, which
  // only runs after the next commit -- too late for handleSubmit's `finally`
  // block below, which needs the just-computed value immediately).
  const messagesRef = useRef<ChatMessageData[]>(messages)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const updateMessages = useCallback(
    (updater: ChatMessageData[] | ((prev: ChatMessageData[]) => ChatMessageData[])) => {
      const next = typeof updater === 'function' ? updater(messagesRef.current) : updater
      messagesRef.current = next
      setMessages(next)
    },
    [],
  )

  const persistChat = useCallback(() => {
    if (!user || !serial || !chatSessionIdRef.current) return
    savePersistedChat(user.username, {
      sessionId: chatSessionIdRef.current,
      machineSerial: serial,
      messages: stripAttachmentsForStorage(messagesRef.current),
      lastMessageAt: Date.now(),
    })
  }, [user, serial])

  const { isStreaming, error: chatError, sendMessage, resumeSessionId } = useChatStream({
    machineSerial: serial,
    onSessionIdChange: (sessionId) => {
      chatSessionIdRef.current = sessionId
      persistChat()
    },
  })

  // Single conversation throughout -- tabs only filter which turns are
  // shown, they never split it into separate threads/session_ids. A user
  // message is matched to its reply via replyToId, since the agent that
  // answered isn't known until the router's step chunk arrives.
  const visibleMessages = useMemo(() => {
    if (activeTab === 'all') return messages
    return messages.filter((message) => {
      if (message.role === 'assistant') return !message.agent || message.agent === activeTab
      const reply = message.replyToId ? messages.find((m) => m.id === message.replyToId) : undefined
      return !reply || !reply.agent || reply.agent === activeTab
    })
  }, [messages, activeTab])

  // Restores the last conversation for this user+machine (if any, and not
  // past the 24h inactivity TTL) once both are known -- this whole component
  // unmounts/remounts on every route change, so without this the chat would
  // reset to the welcome message every time the user navigates away and back.
  useEffect(() => {
    if (!user || !serial) return
    const restoreKey = `${user.username}:${serial}`
    if (restoredKeyRef.current === restoreKey) return
    restoredKeyRef.current = restoreKey

    const persisted = loadPersistedChat(user.username, serial)
    chatSessionIdRef.current = persisted?.sessionId ?? null
    resumeSessionId(persisted?.sessionId ?? null)
    updateMessages(persisted ? persisted.messages : [buildWelcomeMessage(modelLabel, serial)])
  }, [user, serial, modelLabel, resumeSessionId, updateMessages])

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
    const assistantId = `reply-${Date.now()}`
    const userMessage: ChatMessageData = {
      id: `msg-${Date.now()}`,
      role: 'user',
      text: userText,
      attachments: draftAttachments,
      replyToId: assistantId,
    }

    updateMessages((prev) => [
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
          updateMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, text: fullText } : m)),
          )
        },
        onThinkingSteps: (steps) => {
          updateMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, thinkingSteps: steps } : m)),
          )
        },
        onAgent: (agent) => {
          updateMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, agent } : m)))
        },
      })
      if (!reply) {
        updateMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, text: 'No response received from the orchestrator.' }
              : m,
          ),
        )
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Chat request failed.'
      updateMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, text: message } : m)),
      )
    } finally {
      // Covers the fully-settled reply text/thinkingSteps -- onSessionIdChange
      // already persists once early in the turn, but that snapshot only has
      // the user message and an empty placeholder reply.
      persistChat()
    }
  }

  const disabled = machineLoading || !serial || isStreaming
  const statusError = machineError || chatError

  return (
    <div className="chatbot-page">
      <div className="chatbot-page__header">
        <h1>AI Chatbot</h1>
        <p>
          AROL customer platform assistant
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

      <div className="chatbot-page__tabs" role="tablist" aria-label="Filter replies by agent">
        {AGENT_TABS.map((tabOption) => (
          <button
            key={tabOption.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tabOption.id}
            onClick={() => setActiveTab(tabOption.id)}
            className={`chatbot-page__tab${activeTab === tabOption.id ? ' chatbot-page__tab--active' : ''}`}
          >
            {tabOption.label}
          </button>
        ))}
      </div>

      <div className="chatbot-page__messages">
        {visibleMessages.map((message) => (
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

        <div
          role="presentation"
          onClick={() => textareaRef.current?.focus()}
          className="chatbot-page__input-row"
        >
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
            ref={textareaRef}
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
          <button
            type="submit"
            className="chatbot-page__send"
            disabled={disabled || (!draftText.trim() && draftAttachments.length === 0)}
            aria-label="Send message"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        </div>
      </form>
    </div>
  )
}
