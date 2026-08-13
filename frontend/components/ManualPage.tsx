import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMachine, useMachines } from '../src/hooks/useMachine'
import './ManualPage.css'

export default function ManualPage() {
  const { machines, loading: listLoading, error: listError } = useMachines()
  const [selectedSerial, setSelectedSerial] = useState<string | null>(null)

  useEffect(() => {
    if (machines.length > 0 && !selectedSerial) {
      setSelectedSerial(machines[0].serialNumber)
    }
  }, [machines, selectedSerial])

  const { machine, loading, error } = useMachine(selectedSerial)

  if (listLoading || loading) {
    return (
      <div className="manual-page">
        <p className="manual-page__status">Loading manual…</p>
      </div>
    )
  }

  if (listError || error || !machine) {
    return (
      <div className="manual-page">
        <p className="manual-page__status manual-page__status--error">
          {listError || error || 'No machine found for this account.'}
        </p>
      </div>
    )
  }

  const manualUrl = machine.manualUrl

  return (
    <div className="manual-page">
      {machines.length > 1 && (
        <div className="manual-page__picker">
          <label htmlFor="manual-machine-select">Machine manual</label>
          <select
            id="manual-machine-select"
            value={machine.serialNumber}
            onChange={(event) => setSelectedSerial(event.target.value)}
          >
            {machines.map((item) => (
              <option key={item.machineId} value={item.serialNumber}>
                {item.modelCode} · S/N {item.serialNumber} · {item.plantLocation}
              </option>
            ))}
          </select>
        </div>
      )}

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
