import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../src/hooks/useAuth'
import './NavBar.css'

const links = [
  { to: '/machine', label: 'Machine' },
  { to: '/manual', label: 'Manual' },
  { to: '/chatbot', label: 'AI Chatbot' },
]

export default function NavBar() {
  const { user, loading, logout } = useAuth()

  async function handleLogout() {
    await logout()
  }

  return (
    <header className="nav-bar">
      <div className="nav-bar__brand">
        <span className="nav-bar__mark">AROL</span>
        <span className="nav-bar__product">Customer Platform</span>
      </div>
      <nav className="nav-bar__links" aria-label="Main navigation">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/machine'}
            className={({ isActive }) =>
              isActive ? 'nav-bar__link nav-bar__link--active' : 'nav-bar__link'
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
      <div className="nav-bar__auth">
        {loading ? (
          <span className="nav-bar__auth-label">…</span>
        ) : user ? (
          <>
            <Link to="/profile" className="nav-bar__profile" title={user.full_name}>
              {user.full_name}
            </Link>
            <button type="button" className="nav-bar__logout" onClick={handleLogout}>
              Sign out
            </button>
          </>
        ) : null}
      </div>
    </header>
  )
}
