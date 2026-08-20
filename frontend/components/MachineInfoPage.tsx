import { Link } from 'react-router-dom'
import { useActiveMachine } from '../src/hooks/useActiveMachine'
import { useMachine } from '../src/hooks/useMachine'
import './MachineInfoPage.css'

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function displayValue(value: string | number | null | undefined, fallback = '—'): string {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

export default function MachineInfoPage() {
  const { focus } = useActiveMachine()
  const { machine, loading, error } = useMachine(focus?.serialNumber ?? null)

  if (loading) {
    return (
      <div className="machine-page">
        <p className="machine-page__status">Loading machine record…</p>
      </div>
    )
  }

  if (error || !machine) {
    return (
      <div className="machine-page">
        <p className="machine-page__status machine-page__status--error">
          {error || 'No machine found for this account.'}
        </p>
      </div>
    )
  }

  const { model, company } = machine
  const deliveryYear = new Date(machine.deliveryDate).getFullYear()

  return (
    <div className="machine-page">
      <section className="machine-hero">
        <div className="machine-hero__eyebrow">{company.companyName}</div>
        <h1 className="machine-hero__title">{model.modelCode}</h1>
        <p className="machine-hero__subtitle">{model.description}</p>
        <div className="machine-hero__tags">
          <span className="tag">Serial {machine.serialNumber}</span>
          <span className="tag">Delivered {deliveryYear}</span>
          <span className="tag">{model.industrySegment}</span>
          {model.primitiveDiameter !== null && (
            <span className="tag">{model.primitiveDiameter} mm pitch</span>
          )}
          <span className="tag">
            {model.nominalHeads} head{model.nominalHeads === 1 ? '' : 's'}
          </span>
          <span className="tag">{machine.plantLocation}</span>
        </div>
        <p className="machine-hero__description">{machine.configurationProfile}</p>
        <div className="machine-hero__actions">
          <Link to="/manual" className="btn btn--primary">
            Read the manual
          </Link>
          <Link to="/chatbot" className="btn btn--ghost">
            Ask the AI Chatbot
          </Link>
        </div>
      </section>

      <section className="machine-stats">
        <div className="stat-card">
          <span className="stat-card__label">Machine ID</span>
          <span className="stat-card__value stat-card__value--compact">{machine.machineId}</span>
        </div>
        <div className="stat-card">
          <span className="stat-card__label">Delivery date</span>
          <span className="stat-card__value stat-card__value--compact">
            {formatDate(machine.deliveryDate)}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-card__label">PLC family</span>
          <span className="stat-card__value stat-card__value--compact">{machine.plcFamily}</span>
        </div>
        <div className="stat-card">
          <span className="stat-card__label">Software version</span>
          <span className="stat-card__value stat-card__value--compact">
            {displayValue(machine.softwareVersion)}
          </span>
        </div>
      </section>

      <section className="machine-grid">
        <div className="panel">
          <h2>Installation</h2>
          <dl className="def-list">
            <div>
              <dt>Plant location</dt>
              <dd>{machine.plantLocation}</dd>
            </div>
            <div>
              <dt>Delivery date</dt>
              <dd>{formatDate(machine.deliveryDate)}</dd>
            </div>
            <div>
              <dt>Configuration profile</dt>
              <dd>{machine.configurationProfile}</dd>
            </div>
            <div>
              <dt>PLC family</dt>
              <dd>{machine.plcFamily}</dd>
            </div>
            <div>
              <dt>Software version</dt>
              <dd>{displayValue(machine.softwareVersion)}</dd>
            </div>
          </dl>
        </div>

        <div className="panel">
          <h2>Product model</h2>
          <dl className="def-list">
            <div>
              <dt>Model code</dt>
              <dd>{model.modelCode}</dd>
            </div>
            <div>
              <dt>Catalog ID</dt>
              <dd>{model.modelId}</dd>
            </div>
            <div>
              <dt>Industry segment</dt>
              <dd>{model.industrySegment}</dd>
            </div>
            <div>
              <dt>Primitive diameter</dt>
              <dd>
                {model.primitiveDiameter !== null
                  ? `${model.primitiveDiameter} mm`
                  : '—'}
              </dd>
            </div>
            <div>
              <dt>Nominal heads</dt>
              <dd>{model.nominalHeads}</dd>
            </div>
            <div>
              <dt>Container type</dt>
              <dd>{model.containerType}</dd>
            </div>
            <div>
              <dt>Cap type</dt>
              <dd>{model.capType}</dd>
            </div>
          </dl>
        </div>

        <div className="panel">
          <h2>Customer company</h2>
          <dl className="def-list">
            <div>
              <dt>Company</dt>
              <dd>{company.companyName}</dd>
            </div>
            <div>
              <dt>Location</dt>
              <dd>
                {company.city}, {company.country}
              </dd>
            </div>
            <div>
              <dt>Sector</dt>
              <dd>{company.sector}</dd>
            </div>
            <div>
              <dt>Currency</dt>
              <dd>{company.currency}</dd>
            </div>
            <div>
              <dt>Locale</dt>
              <dd>{company.locale}</dd>
            </div>
          </dl>
        </div>

        {model.notes && (
          <div className="panel">
            <h2>Model notes</h2>
            <p className="panel__notes">{model.notes}</p>
          </div>
        )}
      </section>

      {machine.mainUnits.length > 0 && (
        <section className="panel panel--wide">
          <h2>Main units of the machine</h2>
          <div className="units-grid">
            {machine.mainUnits.map((unit) => (
              <div key={unit.code} className="unit-card">
                <span className="unit-card__code">{unit.code}</span>
                <div>
                  <h3>{unit.name}</h3>
                  <p>{unit.note}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
