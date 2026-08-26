import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const homeByRole = {
  PATIENT: '/dashboard',
  DOCTOR: '/doctor',
  HOSPITAL_MANAGER: '/manager',
  SUPERADMIN: '/admin',
}

export default function ProtectedRoute({ allowRole, allowRoles }) {
  const { user } = useAuth()
  const location = useLocation()

  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  const allowed = allowRoles || (allowRole ? [allowRole] : null)
  if (allowed && !allowed.includes(user.role)) {
    return <Navigate to={homeByRole[user.role] || '/dashboard'} replace />
  }
  return <Outlet />
}
