import { useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'
import ChatMessage from './ChatMessage'
import type { ChatAttachment, ChatMessageData } from './ChatMessage'
import './ChatbotPage.css'

const ACCEPTED_TYPES = 'image/*,.txt,.text/plain,.pdf,application/pdf'

const initialMessages: ChatMessageData[] = [
  {
    id: 'welcome',
    role: 'assistant',
    text: "Hi, I'm the AROL assistant for the CLOSYS EAGLE VP (A3279). Ask me about setup, troubleshooting or maintenance, or attach a photo, log file or PDF for more context.",
    attachments: [],
  },
]

function isImage(file: File) {
  return file.type.startsWith('image/')
}

export default function ChatbotPage() {
  const [messages, setMessages] = useState<ChatMessageData[]>(initialMessages)
  const [draftText, setDraftText] = useState('')
  const [draftAttachments, setDraftAttachments] = useState<ChatAttachment[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  function handleSubmit(event: SyntheticEvent) {
    event.preventDefault()
    if (!draftText.trim() && draftAttachments.length === 0) return

    const userMessage: ChatMessageData = {
      id: `msg-${Date.now()}`,
      role: 'user',
      text: draftText.trim(),
      attachments: draftAttachments,
    }
    setMessages((prev) => [...prev, userMessage])
    setDraftText('')
    setDraftAttachments([])
    setIsThinking(true)

    // Placeholder reply: the orchestrator/AI agents backend is not wired up yet in this concept.
    window.setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: `reply-${Date.now()}`,
          role: 'assistant',
          text:
            userMessage.attachments.length > 0
              ? "Thanks, I've received your attachment. Once the AI agents backend is connected I'll analyze it and reply with guidance."
              : "This is a front-end concept, so I can't reason about that yet — the orchestrator and AI agents backend will plug in here.",
          attachments: [],
        },
      ])
      setIsThinking(false)
    }, 700)
  }

  return (
    <div className="chatbot-page">
      <div className="chatbot-page__header">
        <h1>AI Chatbot</h1>
        <p>Troubleshooting support for the CLOSYS EAGLE VP &middot; Serial A3279</p>
      </div>

      <div className="chatbot-page__messages">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {isThinking && (
          <div className="chatbot-page__thinking">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        )}
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
            placeholder="Ask about setup, maintenance or troubleshooting..."
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit(e)
              }
            }}
            rows={1}
          />
          <button type="submit" className="btn btn--primary">
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
