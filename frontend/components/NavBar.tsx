import { NavLink } from 'react-router-dom'
import './NavBar.css'

const links = [
  { to: '/', label: 'Machine' },
  { to: '/manual', label: 'Manual' },
  { to: '/chatbot', label: 'AI Chatbot' },
]

export default function NavBar() {
  return (
    <header className="nav-bar">
      <div className="nav-bar__brand">
        <span className="nav-bar__mark">AROL</span>
        <span className="nav-bar__product">Customer Platform</span>
      </div>
      <nav className="nav-bar__links">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/'}
            className={({ isActive }) =>
              isActive ? 'nav-bar__link nav-bar__link--active' : 'nav-bar__link'
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
    </header>
  )
}
