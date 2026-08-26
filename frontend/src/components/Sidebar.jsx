import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navByRole = {
  PATIENT: [
    ['Overview', '/dashboard', '⌂'], ['Book visit', '/book', '+'], ['My bookings', '/dashboard#appointments', '▣'], ['Visit prep', '/dashboard#appointments', '✦'],
  ],
  DOCTOR: [
    ['Home', '/doctor', '⌂'], ['Schedule', '/doctor#schedule', '▣'], ['Patients', '/doctor#schedule', '♙'], ['Care team', '/doctor#schedule', '✦'],
  ],
  HOSPITAL_MANAGER: [
    ['Home', '/manager', '⌂'], ['Doctors', '/manager#team', '♙'], ['Patients', '/manager#patients', '◌'], ['Bookings', '/manager#bookings', '▣'],
  ],
  SUPERADMIN: [
    ['Home', '/admin', '⌂'], ['Managers', '/admin#team', '♙'], ['Patients', '/admin#patients', '◌'], ['Bookings', '/admin#bookings', '▣'],
  ],
}

export default function Sidebar() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const touch = useRef(null)
  const items = navByRole[user?.role] || []
  useEffect(() => {
    const toggle = () => setOpen((value) => !value)
    window.addEventListener('citycare:toggle-nav', toggle)
    return () => window.removeEventListener('citycare:toggle-nav', toggle)
  }, [])
  const start = (event) => { touch.current = event.touches[0].clientX }
  const end = (event) => {
    if (touch.current === null) return
    const distance = event.changedTouches[0].clientX - touch.current
    if (touch.current < 34 && distance > 55) setOpen(true)
    if (open && distance < -55) setOpen(false)
    touch.current = null
  }
  return <><div className={`sidebar-scrim ${open ? 'sidebar-scrim-visible' : ''}`} onClick={() => setOpen(false)} />
    <aside className={`app-sidebar ${open ? 'app-sidebar-open' : ''}`} onTouchStart={start} onTouchEnd={end} aria-label="CityCare navigation">
      <div className="sidebar-brand"><span className="brand-orb">+</span><div><strong>CityCare</strong><small>Clinic workspace</small></div></div>
      <div className="sidebar-person"><span>{user?.first_name?.slice(0, 1) || 'C'}</span><div><strong>{user?.first_name} {user?.last_name}</strong><small>{String(user?.role || '').replaceAll('_', ' ').toLowerCase()}</small></div></div>
      <p className="sidebar-caption">Workspace</p><nav>{items.map(([label, to, icon]) => <NavLink key={label} to={to} onClick={() => setOpen(false)} className="sidebar-link"><span>{icon}</span>{label}</NavLink>)}</nav>
      <div className="sidebar-tip"><span>↔</span><p>Swipe from the left edge to open this menu on mobile.</p></div>
    </aside></>
}
