import { machine } from '../src/data/machine'
import './ManualPage.css'

export default function ManualPage() {
  return (
    <div className="manual-page">
      <div className="manual-page__bar">
        <div>
          <h1>Use &amp; maintenance manual</h1>
          <p>
            {machine.model} &middot; Serial {machine.serialNumber} &middot; Rev.{' '}
            {machine.manualRevision} ({machine.manualDate})
          </p>
        </div>
        <a className="btn btn--primary" href={machine.manualUrl} target="_blank" rel="noreferrer">
          Open in new tab
        </a>
      </div>

      <object data={machine.manualUrl} type="application/pdf" className="manual-page__viewer">
        <div className="manual-page__fallback">
          <p>Your browser can&apos;t preview PDFs inline.</p>
          <a className="btn btn--primary" href={machine.manualUrl} target="_blank" rel="noreferrer">
            Download the manual
          </a>
        </div>
      </object>
    </div>
  )
}
