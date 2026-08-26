import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Navbar() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    signOut()
    navigate('/login', { replace: true })
  }
  const homeByRole = { PATIENT: '/dashboard', DOCTOR: '/doctor', HOSPITAL_MANAGER: '/manager', SUPERADMIN: '/admin' }
  const roleLabel = { PATIENT: 'Patient portal', DOCTOR: 'Doctor portal', HOSPITAL_MANAGER: 'Hospital manager', SUPERADMIN: 'Superadmin' }

  return (
    <header className="sticky top-0 z-30 border-b border-white/50 bg-slate-50/80 backdrop-blur-xl">
      <nav className="page-shell flex min-h-16 items-center justify-between gap-4" aria-label="Main navigation">
        <div className="flex items-center gap-3"><button type="button" className="nav-menu-button" aria-label="Open navigation" onClick={() => window.dispatchEvent(new Event('citycare:toggle-nav'))}><span /><span /><span /></button><Link to={homeByRole[user?.role] || '/dashboard'} className="group flex items-center gap-2 font-black tracking-tight text-ink">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand to-aqua text-xl text-white shadow-lg shadow-brand/25 transition group-hover:rotate-6">+</span>
          <span>CityCare <span className="font-medium text-slate-500">Clinic</span></span>
        </Link></div>
        {user && (
          <div className="flex items-center gap-2 sm:gap-4">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-bold text-ink">{user.first_name}</p>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-brand">{roleLabel[user.role] || 'CityCare portal'}</p>
            </div>
            <button type="button" onClick={handleLogout} className="button-secondary px-3 py-2 text-sm">Log out</button>
          </div>
        )}
      </nav>
    </header>
  )
}
