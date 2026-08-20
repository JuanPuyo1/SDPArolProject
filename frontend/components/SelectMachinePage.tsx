import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fetchMachine } from '../src/api/machines'
import { useActiveMachine } from '../src/hooks/useActiveMachine'
import { useMachines } from '../src/hooks/useMachine'
import './SelectMachinePage.css'

export default function SelectMachinePage() {
  const { machines, loading, error } = useMachines()
  const { setFocusFromMachine } = useActiveMachine()
  const navigate = useNavigate()

  const [pickError, setPickError] = useState<string | null>(null)

  async function chooseSerial(serialNumber: string) {
    setPickError(null)
    try {
      const machine = await fetchMachine(serialNumber)
      setFocusFromMachine(machine, 'list')
      navigate('/machine', { replace: true })
    } catch (err: unknown) {
      setPickError(err instanceof Error ? err.message : 'Could not open that machine.')
    }
  }

  return (
    <div className="select-machine">
      <header className="select-machine__header">
        <div className="select-machine__eyebrow">Machine access</div>
        <h1 className="select-machine__title">Choose a machine</h1>
        <p className="select-machine__lead">
          Scan the QR code on the equipment, or pick a machine assigned to your
          company.
        </p>
        <Link to="/scan" className="btn btn--primary select-machine__scan">
          Scan QR code
        </Link>
      </header>

      {loading && <p className="select-machine__status">Loading your fleet…</p>}
      {pickError && (
        <p className="select-machine__status select-machine__status--error">{pickError}</p>
      )}
      {error && (
        <p className="select-machine__status select-machine__status--error">{error}</p>
      )}

      {!loading && !error && machines.length === 0 && (
        <p className="select-machine__status">No machines are assigned to this account.</p>
      )}

      {!loading && !error && machines.length > 0 && (
        <ul className="select-machine__list">
          {machines.map((item) => (
            <li key={item.machineId}>
              <button
                type="button"
                className="select-machine__card"
                onClick={() => void chooseSerial(item.serialNumber)}
              >
                <span className="select-machine__model">{item.modelCode}</span>
                <span className="select-machine__meta">
                  S/N {item.serialNumber} · {item.plantLocation}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
