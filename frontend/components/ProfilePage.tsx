import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { updateProfile } from '../src/api/auth'
import { useAuth } from '../src/hooks/useAuth'
import './ProfilePage.css'

export default function ProfilePage() {
  const { user, logout, refreshUser } = useAuth()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (user) {
      setFirstName(user.first_name)
      setLastName(user.last_name)
      setEmail(user.email)
    }
  }, [user])

  if (!user) return null

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setMessage(null)
    setError(null)
    setSaving(true)
    try {
      await updateProfile({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
      })
      await refreshUser()
      setMessage('Profile updated.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleLogout() {
    await logout()
  }

  return (
    <div className="profile-page">
      <section className="profile-hero">
        <div className="profile-hero__eyebrow">Account</div>
        <h1 className="profile-hero__title">{user.full_name}</h1>
        <p className="profile-hero__subtitle">Signed in as @{user.username}</p>
        <div className="profile-hero__tags">
          <span className="tag">User ID {user.id}</span>
          {user.is_staff && <span className="tag">Staff</span>}
        </div>
      </section>

      <div className="profile-grid">
        <section className="panel">
          <h2 className="panel__title">Session details</h2>
          <dl className="profile-dl">
            <div>
              <dt>Username</dt>
              <dd>{user.username}</dd>
            </div>
            <div>
              <dt>Member since</dt>
              <dd>{new Date(user.date_joined).toLocaleDateString()}</dd>
            </div>
            <div>
              <dt>Last login</dt>
              <dd>
                {user.last_login
                  ? new Date(user.last_login).toLocaleString()
                  : 'First session'}
              </dd>
            </div>
          </dl>
        </section>

        <section className="panel">
          <h2 className="panel__title">Edit profile</h2>
          <form className="profile-form" onSubmit={handleSubmit}>
            <label className="profile-form__field">
              <span>First name</span>
              <input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
            </label>
            <label className="profile-form__field">
              <span>Last name</span>
              <input
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </label>
            <label className="profile-form__field">
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>

            {message && <p className="profile-form__message">{message}</p>}
            {error && <p className="profile-form__error">{error}</p>}

            <div className="profile-form__actions">
              <button type="submit" className="btn btn--primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
              <button type="button" className="btn btn--ghost" onClick={handleLogout}>
                Sign out
              </button>
            </div>
          </form>
        </section>
      </div>

      <Link to="/machine" className="profile-page__back">
        Back to machine view
      </Link>
    </div>
  )
}
