import './ChatMessage.css'

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
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function ChatMessage({ message }: { message: ChatMessageData }) {
  return (
    <div className={`chat-message chat-message--${message.role}`}>
      <div className="chat-message__avatar">{message.role === 'user' ? 'You' : 'AI'}</div>
      <div className="chat-message__body">
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
        {message.text && <p className="chat-message__text">{message.text}</p>}
      </div>
    </div>
  )
}
