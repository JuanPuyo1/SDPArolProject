import { Link } from 'react-router-dom'
import { useDefaultMachine } from '../src/hooks/useMachine'
import './MachineInfoPage.css'

export default function MachineInfoPage() {
  const { machine, loading, error } = useDefaultMachine()

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

  return (
    <div className="machine-page">
      <section className="machine-hero">
        <div className="machine-hero__eyebrow">Machine record</div>
        <h1 className="machine-hero__title">{machine.model}</h1>
        <p className="machine-hero__subtitle">{machine.fullModel}</p>
        <div className="machine-hero__tags">
          <span className="tag">Serial {machine.serialNumber}</span>
          <span className="tag">{machine.manufacturingYear}</span>
          <span className="tag">{machine.identification.pitchDiameter} pitch</span>
          <span className="tag">{machine.identification.heads} head</span>
        </div>
        <p className="machine-hero__description">{machine.description}</p>
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
          <span className="stat-card__label">Machine weight</span>
          <span className="stat-card__value">
            {machine.technicalData.weight.value} {machine.technicalData.weight.unit}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-card__label">Productive capacity</span>
          <span className="stat-card__value">
            {machine.technicalData.productiveCapacity.value}{' '}
            {machine.technicalData.productiveCapacity.unit}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-card__label">Total installed power</span>
          <span className="stat-card__value">{machine.technicalData.electrical.totalInstalledPower}</span>
        </div>
        <div className="stat-card">
          <span className="stat-card__label">Rotation</span>
          <span className="stat-card__value">{machine.identification.rotation}</span>
        </div>
      </section>

      <section className="machine-grid">
        <div className="panel">
          <h2>Identification</h2>
          <dl className="def-list">
            <div>
              <dt>Manufacturer</dt>
              <dd>
                {machine.manufacturer} &middot; {machine.site}
              </dd>
            </div>
            <div>
              <dt>Machine type</dt>
              <dd>{machine.identification.machineType}</dd>
            </div>
            <div>
              <dt>Pitch diameter</dt>
              <dd>{machine.identification.pitchDiameter}</dd>
            </div>
            <div>
              <dt>Number of heads</dt>
              <dd>{machine.identification.heads}</dd>
            </div>
            <div>
              <dt>Manual revision</dt>
              <dd>
                Rev. {machine.manualRevision} &middot; {machine.manualDate}
              </dd>
            </div>
          </dl>
        </div>

        <div className="panel">
          <h2>Electrical data</h2>
          <dl className="def-list">
            <div>
              <dt>Main supply</dt>
              <dd>{machine.technicalData.electrical.mainSupply}</dd>
            </div>
            <div>
              <dt>Auxiliary supply</dt>
              <dd>{machine.technicalData.electrical.auxiliarySupply}</dd>
            </div>
            {machine.technicalData.electrical.breakdown.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="panel">
          <h2>Pneumatic data</h2>
          <dl className="def-list">
            <div>
              <dt>Sterile air capacity</dt>
              <dd>{machine.technicalData.pneumatic.sterileAirCapacity}</dd>
            </div>
            <div>
              <dt>Min. pressure</dt>
              <dd>{machine.technicalData.pneumatic.minPressure}</dd>
            </div>
            <div>
              <dt>Max. pressure</dt>
              <dd>{machine.technicalData.pneumatic.maxPressure}</dd>
            </div>
          </dl>
        </div>

        <div className="panel">
          <h2>Operating conditions</h2>
          <dl className="def-list">
            <div>
              <dt>Temperature range</dt>
              <dd>{machine.operatingConditions.temperature}</dd>
            </div>
            <div>
              <dt>Environment</dt>
              <dd>{machine.operatingConditions.environment}</dd>
            </div>
            <div>
              <dt>Noise emission</dt>
              <dd>{machine.operatingConditions.noise}</dd>
            </div>
          </dl>
          <div className="cert-badges">
            {machine.certifications.map((cert) => (
              <span key={cert} className="cert-badge">
                {cert}
              </span>
            ))}
          </div>
        </div>
      </section>

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
    </div>
  )
}
