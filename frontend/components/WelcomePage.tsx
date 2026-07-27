import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../src/hooks/useAuth'
import './WelcomePage.css'

export default function WelcomePage() {
  const { user, loading, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/machine'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (loading) {
    return (
      <div className="welcome-page welcome-page--loading">
        <p className="welcome-page__loading">Loading…</p>
      </div>
    )
  }

  if (user) {
    return <Navigate to={from} replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="welcome-page">
      <section className="welcome-hero">
        <div className="welcome-hero__brand">
          <span className="welcome-hero__mark">AROL</span>
          <span className="welcome-hero__product">Customer Platform</span>
        </div>
        <h1 className="welcome-hero__title">Welcome to your machine support hub</h1>
        <p className="welcome-hero__lead">
          Access digital manuals, AI-assisted troubleshooting, and service tools for your
          AROL capping machines — all in one place.
        </p>
        <ul className="welcome-hero__features">
          <li>Interactive machine records and maintenance manuals</li>
          <li>QR-linked access from the plant floor</li>
          <li>Governed AI support scoped to your equipment</li>
        </ul>
      </section>

      <section className="welcome-login">
        <div className="welcome-login__card">
          <div className="welcome-login__eyebrow">Sign in</div>
          <h2 className="welcome-login__title">Access your account</h2>
          <p className="welcome-login__subtitle">
            Enter your credentials to view your machines and platform tools.
          </p>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="auth-form__field">
              <span>Username</span>
              <input
                type="text"
                name="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </label>

            <label className="auth-form__field">
              <span>Password</span>
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>

            {error && <p className="auth-form__error">{error}</p>}

            <button type="submit" className="btn btn--primary auth-form__submit" disabled={submitting}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="welcome-login__footer">
            Need an account? Contact your administrator to create a platform user.
          </p>
        </div>
      </section>
    </div>
  )
}
