import { useCallback, useEffect, useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'
import ChatMessage from './ChatMessage'
import type { ChatAttachment, ChatMessageData } from './ChatMessage'
import { useAuth } from '../src/hooks/useAuth'
import { useActiveMachine } from '../src/hooks/useActiveMachine'
import { useMachine } from '../src/hooks/useMachine'
import { useChatStream } from '../src/hooks/useChat'
import {
  loadPersistedChat,
  savePersistedChat,
  MAX_SESSIONS,
  type PersistedSession,
} from '../src/api/chatStorage'
// @ts-expect-error Side-effect CSS import resolved by bundler
import './ChatbotPage.css'

const ACCEPTED_TYPES = 'image/*,.txt,.text/plain,.pdf,application/pdf'

type Session = PersistedSession

type ChatState = {
  sessions: Session[]
  activeSessionId: string | null
}

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

function createSessionData(model: string, serial: string): Session {
  return {
    id: `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    sessionId: null,
    messages: [buildWelcomeMessage(model, serial)],
    lastMessageAt: Date.now(),
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
  const { focus } = useActiveMachine()
  const { machine, loading: machineLoading, error: machineError } = useMachine(
    focus?.serialNumber ?? null,
  )
  const serial = machine?.serialNumber ?? null
  const modelLabel = machine?.model.modelCode ?? 'your machine'

  const [chatState, setChatState] = useState<ChatState>({ sessions: [], activeSessionId: null })
  const [draftText, setDraftText] = useState('')
  const [draftAttachments, setDraftAttachments] = useState<ChatAttachment[]>([])
  const restoredKeyRef = useRef<string | null>(null)
  // Mirrors `chatState`, but updated synchronously (not via a useEffect,
  // which only runs after the next commit -- too late for handleSubmit's
  // `finally` block and the various session-management callbacks below,
  // which all need the just-computed value immediately).
  const chatStateRef = useRef<ChatState>(chatState)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const updateChatState = useCallback(
    (updater: ChatState | ((prev: ChatState) => ChatState)) => {
      const next = typeof updater === 'function' ? updater(chatStateRef.current) : updater
      chatStateRef.current = next
      setChatState(next)
    },
    [],
  )

  const persistChat = useCallback(() => {
    const { sessions, activeSessionId } = chatStateRef.current
    if (!user || !serial || !activeSessionId) return
    savePersistedChat(user.username, {
      machineSerial: serial,
      activeSessionId,
      sessions: sessions.map((s) => ({ ...s, messages: stripAttachmentsForStorage(s.messages) })),
    })
  }, [user, serial])

  const updateActiveSessionMessages = useCallback(
    (updater: (prev: ChatMessageData[]) => ChatMessageData[]) => {
      updateChatState((prev) => {
        if (!prev.activeSessionId) return prev
        return {
          ...prev,
          sessions: prev.sessions.map((s) =>
            s.id === prev.activeSessionId
              ? { ...s, messages: updater(s.messages), lastMessageAt: Date.now() }
              : s,
          ),
        }
      })
    },
    [updateChatState],
  )

  const { isStreaming, error: chatError, sendMessage, resumeSessionId, abort } = useChatStream({
    machineSerial: serial,
    onSessionIdChange: (sessionId) => {
      updateChatState((prev) => {
        if (!prev.activeSessionId) return prev
        return {
          ...prev,
          sessions: prev.sessions.map((s) =>
            s.id === prev.activeSessionId ? { ...s, sessionId } : s,
          ),
        }
      })
      persistChat()
    },
  })

  const activeSession = chatState.sessions.find((s) => s.id === chatState.activeSessionId) ?? null

  // Restores this user+machine's sessions (if any, and not past the 24h
  // inactivity TTL) once both are known -- this whole component
  // unmounts/remounts on every route change, so without this the chat would
  // reset to a single fresh session every time the user navigates away and
  // back.
  useEffect(() => {
    if (!user || !serial) return
    const restoreKey = `${user.username}:${serial}`
    if (restoredKeyRef.current === restoreKey) return
    restoredKeyRef.current = restoreKey

    const persisted = loadPersistedChat(user.username, serial)
    const sessions = persisted?.sessions.length ? persisted.sessions : [createSessionData(modelLabel, serial)]
    const activeSessionId = persisted?.sessions.length ? persisted.activeSessionId : sessions[0].id

    updateChatState({ sessions, activeSessionId })
    resumeSessionId(sessions.find((s) => s.id === activeSessionId)?.sessionId ?? null)
  }, [user, serial, modelLabel, resumeSessionId, updateChatState])

  const createSession = useCallback(() => {
    if (!serial || chatStateRef.current.sessions.length >= MAX_SESSIONS) return
    const session = createSessionData(modelLabel, serial)
    abort()
    updateChatState((prev) => ({ sessions: [...prev.sessions, session], activeSessionId: session.id }))
    resumeSessionId(null)
    persistChat()
  }, [serial, modelLabel, abort, updateChatState, resumeSessionId, persistChat])

  const switchSession = useCallback(
    (id: string) => {
      if (id === chatStateRef.current.activeSessionId) return
      abort()
      const target = chatStateRef.current.sessions.find((s) => s.id === id)
      updateChatState((prev) => ({ ...prev, activeSessionId: id }))
      resumeSessionId(target?.sessionId ?? null)
      persistChat()
    },
    [abort, updateChatState, resumeSessionId, persistChat],
  )

  const restartSession = useCallback(
    (id: string) => {
      if (!serial) return
      const isActive = id === chatStateRef.current.activeSessionId
      if (isActive) abort()
      updateChatState((prev) => ({
        ...prev,
        sessions: prev.sessions.map((s) =>
          s.id === id
            ? { id, sessionId: null, messages: [buildWelcomeMessage(modelLabel, serial)], lastMessageAt: Date.now() }
            : s,
        ),
      }))
      if (isActive) resumeSessionId(null)
      persistChat()
    },
    [serial, modelLabel, abort, updateChatState, resumeSessionId, persistChat],
  )

  const closeSession = useCallback(
    (id: string) => {
      if (chatStateRef.current.sessions.length <= 1) return
      const wasActive = id === chatStateRef.current.activeSessionId
      if (wasActive) abort()
      updateChatState((prev) => {
        const sessions = prev.sessions.filter((s) => s.id !== id)
        const activeSessionId = prev.activeSessionId === id ? sessions[0].id : prev.activeSessionId
        return { sessions, activeSessionId }
      })
      if (wasActive) {
        const { sessions, activeSessionId } = chatStateRef.current
        resumeSessionId(sessions.find((s) => s.id === activeSessionId)?.sessionId ?? null)
      }
      persistChat()
    },
    [abort, updateChatState, resumeSessionId, persistChat],
  )

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
    if (!serial || !activeSession || isStreaming) return

    const userText = draftText.trim()
    const assistantId = `reply-${Date.now()}`
    const userMessage: ChatMessageData = {
      id: `msg-${Date.now()}`,
      role: 'user',
      text: userText,
      attachments: draftAttachments,
    }

    updateActiveSessionMessages((prev) => [
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
          updateActiveSessionMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, text: fullText } : m)),
          )
        },
        onThinkingSteps: (steps) => {
          updateActiveSessionMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, thinkingSteps: steps } : m)),
          )
        },
        onAgent: (agent) => {
          updateActiveSessionMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, agent } : m)),
          )
        },
      })
      if (!reply) {
        updateActiveSessionMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, text: 'No response received from the orchestrator.' }
              : m,
          ),
        )
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Chat request failed.'
      updateActiveSessionMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, text: message } : m)),
      )
    } finally {
      // Covers the fully-settled reply text/thinkingSteps -- onSessionIdChange
      // already persists once early in the turn, but that snapshot only has
      // the user message and an empty placeholder reply.
      persistChat()
    }
  }

  const disabled = machineLoading || !serial || !activeSession || isStreaming
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

      <div className="chatbot-page__session-tabs" role="tablist" aria-label="Chat sessions">
        {chatState.sessions.map((session, index) => {
          const isActive = session.id === chatState.activeSessionId
          return (
            <div
              key={session.id}
              className={`chatbot-page__session-tab${isActive ? ' chatbot-page__session-tab--active' : ''}`}
            >
              <button
                type="button"
                role="tab"
                aria-selected={isActive}
                className="chatbot-page__session-tab-label"
                onClick={() => switchSession(session.id)}
              >
                Chat {index + 1}
              </button>
              <button
                type="button"
                className="chatbot-page__session-tab-action"
                onClick={() => restartSession(session.id)}
                aria-label={`Restart chat ${index + 1}`}
                title="Restart this conversation"
              >
                ↻
              </button>
              {chatState.sessions.length > 1 && (
                <button
                  type="button"
                  className="chatbot-page__session-tab-action chatbot-page__session-tab-close"
                  onClick={() => closeSession(session.id)}
                  aria-label={`Close chat ${index + 1}`}
                  title="Close this conversation"
                >
                  ×
                </button>
              )}
            </div>
          )
        })}
        {chatState.sessions.length < MAX_SESSIONS && (
          <button
            type="button"
            className="chatbot-page__session-tab-new"
            onClick={createSession}
            disabled={!serial}
            aria-label="Start a new chat"
            title="Start a new chat"
          >
            + New chat
          </button>
        )}
      </div>

      <div className="chatbot-page__messages">
        {(activeSession?.messages ?? []).map((message) => (
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
