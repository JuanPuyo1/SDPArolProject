import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../src/hooks/useAuth'
import type { UserVisibility } from '../src/types/auth'
import './NavBar.css'

type NavLinkItem = {
  to: string
  label: string
  roles?: UserVisibility[]
}

const links: NavLinkItem[] = [
  { to: '/machine', label: 'Machine' },
  { to: '/manual', label: 'Manual' },
  { to: '/orders', label: 'Orders', roles: ['full', 'commercial'] },
  {
    to: '/maintenance',
    label: 'Maintenance tickets',
    roles: ['full', 'technician'],
  },
  { to: '/chatbot', label: 'AI Chatbot' },
]

export default function NavBar() {
  const { user, loading, logout } = useAuth()

  async function handleLogout() {
    await logout()
  }

  const visibleLinks = links.filter((link) => {
    if (!link.roles) return true
    return !!user?.visibility && link.roles.includes(user.visibility)
  })

  return (
    <header className="nav-bar">
      <div className="nav-bar__brand">
        <span className="nav-bar__mark">AROL</span>
        <span className="nav-bar__product">Customer Platform</span>
      </div>
      <nav className="nav-bar__links" aria-label="Main navigation">
        {visibleLinks.map((link) => (
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
