import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { AnchorHTMLAttributes } from 'react'
import { AGENT_LABELS, formatStepDuration, type ThinkingStep } from '../src/api/chat'
import './ChatMessage.css'

// react-markdown never interprets raw HTML in the source by default (no
// rehype-raw plugin here) -- the model's output, including anything sourced
// from retrieved manuals or tool results, is rendered as text/markdown only,
// never as live HTML. Only this small link override is customized, to open
// externally and avoid a reverse-tabnabbing target="_blank" without rel.
function MarkdownLink({ children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a {...props} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  )
}

export interface ChatAttachment {
  id: string
  file: File
  previewUrl: string | null
}

export interface ChatMessageData {
  id: string
  role: 'user' | 'assistant'
  text: string
  attachments: ChatAttachment[]
  thinkingSteps?: ThinkingStep[]
  // Which agent produced this reply (e.g. 'orders_business'), set once the
  // router's step chunk arrives. Undefined for the welcome message, user
  // messages, and anything from the router-less stub backend.
  agent?: string
}

function agentLabel(agent: string): string {
  return AGENT_LABELS[agent] ?? agent
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function ThinkingChain({ steps }: { steps: ThinkingStep[] }) {
  if (steps.length === 0) return null

  return (
    <div className="thinking-chain" aria-label="Agent activity">
      <div className="thinking-chain__title">Agent activity</div>
      <ol className="thinking-chain__list">
        {steps.map((step) => {
          const duration = formatStepDuration(step.durationMs)
          return (
            <li
              key={step.id}
              className={`thinking-chain__item thinking-chain__item--${step.status}`}
            >
              <span className="thinking-chain__indicator" aria-hidden="true" />
              <div className="thinking-chain__content">
                <div className="thinking-chain__heading">
                  <span className="thinking-chain__label">{step.label}</span>
                  {step.tool && <span className="thinking-chain__tool">{step.tool}</span>}
                  {duration && <span className="thinking-chain__duration">for {duration}</span>}
                </div>
                {step.detail && <span className="thinking-chain__detail">{step.detail}</span>}
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export default function ChatMessage({ message }: { message: ChatMessageData }) {
  const showThinking = message.role === 'assistant' && (message.thinkingSteps?.length ?? 0) > 0

  return (
    <div className={`chat-message chat-message--${message.role}`}>
      <div className="chat-message__avatar">{message.role === 'user' ? 'You' : 'AI'}</div>
      <div className="chat-message__body">
        {message.role === 'assistant' && message.agent && (
          <span className="chat-message__agent-badge">{agentLabel(message.agent)}</span>
        )}
        {showThinking && message.thinkingSteps && (
          <ThinkingChain steps={message.thinkingSteps} />
        )}
        {message.attachments.length > 0 && (
          <div className="chat-message__attachments">
            {message.attachments.map((att) =>
              att.previewUrl ? (
                <img key={att.id} src={att.previewUrl} alt={att.file.name} className="chat-attachment__image" />
              ) : (
                <div key={att.id} className="chat-attachment__file">
                  <span className="chat-attachment__ext">
                    {att.file.name.split('.').pop()?.toUpperCase()}
                  </span>
                  <div>
                    <div className="chat-attachment__name">{att.file.name}</div>
                    <div className="chat-attachment__size">{formatSize(att.file.size)}</div>
                  </div>
                </div>
              ),
            )}
          </div>
        )}
        {message.text && (
          <div className="chat-message__text">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: MarkdownLink }}>
              {message.text}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}
