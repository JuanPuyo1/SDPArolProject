import { Link } from 'react-router-dom'
import { useActiveMachine } from '../src/hooks/useActiveMachine'
import { useMachine } from '../src/hooks/useMachine'
import './ManualPage.css'

export default function ManualPage() {
  const { focus } = useActiveMachine()
  const { machine, loading, error } = useMachine(focus?.serialNumber ?? null)

  if (loading) {
    return (
      <div className="manual-page">
        <p className="manual-page__status">Loading manual…</p>
      </div>
    )
  }

  if (error || !machine) {
    return (
      <div className="manual-page">
        <p className="manual-page__status manual-page__status--error">
          {error || 'No machine found for this account.'}
        </p>
      </div>
    )
  }

  const manualUrl = machine.manualUrl

  return (
    <div className="manual-page">
      <div className="manual-page__bar">
        <div>
          <h1>Use &amp; maintenance manual</h1>
          <p>
            {machine.model.modelCode} &middot; Serial {machine.serialNumber} &middot;{' '}
            {machine.plantLocation}
          </p>
        </div>
        {manualUrl && (
          <a className="btn btn--primary" href={manualUrl} target="_blank" rel="noreferrer">
            Open in new tab
          </a>
        )}
      </div>

      {manualUrl ? (
        <object data={manualUrl} type="application/pdf" className="manual-page__viewer">
          <div className="manual-page__fallback">
            <p>Your browser can&apos;t preview PDFs inline.</p>
            <a className="btn btn--primary" href={manualUrl} target="_blank" rel="noreferrer">
              Download the manual
            </a>
          </div>
        </object>
      ) : (
        <div className="manual-page__fallback manual-page__fallback--prominent">
          <p>
            No PDF manual is available for serial <strong>{machine.serialNumber}</strong> (
            {machine.model.modelCode}). You can still search procedures and error codes with the AI
            assistant.
          </p>
          <Link to="/chatbot" className="btn btn--primary">
            Open AI Chatbot
          </Link>
        </div>
      )}
    </div>
  )
}
