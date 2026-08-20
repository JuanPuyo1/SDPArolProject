import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Html5Qrcode } from 'html5-qrcode'
import { Link, useNavigate } from 'react-router-dom'
import { fetchMachine } from '../src/api/machines'
import { parseMachineIdFromQr } from '../src/api/qrMachineId'
import { useActiveMachine } from '../src/hooks/useActiveMachine'
import './SelectMachinePage.css'
import './ScanQrPage.css'

export default function ScanQrPage() {
  const { setFocusFromMachine } = useActiveMachine()
  const navigate = useNavigate()
  const [paste, setPaste] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const readerId = 'qr-reader'
  const scannerRef = useRef<Html5Qrcode | null>(null)
  const resolvingRef = useRef(false)

  async function resolveIdentifier(raw: string) {
    if (resolvingRef.current) return
    const identifier = parseMachineIdFromQr(raw)
    if (!identifier) {
      setError('Could not read a machine id from that QR code.')
      return
    }

    resolvingRef.current = true
    setBusy(true)
    setError(null)
    try {
      await scannerRef.current?.stop().catch(() => undefined)
      const machine = await fetchMachine(identifier)
      setFocusFromMachine(machine, 'qr')
      navigate('/machine', { replace: true })
    } catch (err: unknown) {
      resolvingRef.current = false
      setError(err instanceof Error ? err.message : 'Could not open this machine.')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    const scanner = new Html5Qrcode(readerId)
    scannerRef.current = scanner

    scanner
      .start(
        { facingMode: 'environment' },
        { fps: 8, qrbox: { width: 240, height: 240 } },
        (decoded) => {
          void resolveIdentifier(decoded)
        },
        () => undefined,
      )
      .catch(() => {
        setError(
          'Camera is unavailable. Paste the QR URL or upload a photo of the code instead.',
        )
      })

    return () => {
      void scanner.stop().catch(() => undefined)
      scanner.clear()
      scannerRef.current = null
    }
    // resolveIdentifier is stable enough for mount/unmount scanner lifecycle
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handlePaste(event: FormEvent) {
    event.preventDefault()
    await resolveIdentifier(paste)
  }

  async function handleFile(file: File | undefined) {
    if (!file) return
    setError(null)
    setBusy(true)
    try {
      await scannerRef.current?.stop().catch(() => undefined)
      const scanner = scannerRef.current ?? new Html5Qrcode(readerId)
      const decoded = await scanner.scanFile(file, true)
      await resolveIdentifier(decoded)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not read that image.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="scan-qr">
      <header className="scan-qr__header">
        <div className="select-machine__eyebrow">QR access</div>
        <h1 className="select-machine__title">Scan a machine QR</h1>
        <p className="select-machine__lead">
          Point the camera at the code on the machine, or paste the URL / upload a
          photo.
        </p>
        <Link to="/select" className="btn btn--ghost">
          Back to machine list
        </Link>
      </header>

      <div id={readerId} className="scan-qr__viewport" />

      {error && <p className="select-machine__status select-machine__status--error">{error}</p>}
      {busy && <p className="select-machine__status">Opening machine…</p>}

      <form className="scan-qr__form" onSubmit={(event) => void handlePaste(event)}>
        <label htmlFor="qr-paste">Paste QR URL or serial</label>
        <input
          id="qr-paste"
          type="text"
          value={paste}
          onChange={(event) => setPaste(event.target.value)}
          placeholder="https://…/m/17478 or A3279"
        />
        <button type="submit" className="btn btn--primary" disabled={busy || !paste.trim()}>
          Open machine
        </button>
      </form>

      <label className="scan-qr__file">
        Upload QR image
        <input
          type="file"
          accept="image/*"
          onChange={(event) => void handleFile(event.target.files?.[0])}
        />
      </label>
    </div>
  )
}
