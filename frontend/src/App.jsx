import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'
import Sidebar from './components/Sidebar'
import AssistantPanel from './components/AssistantPanel'
import { useAuth } from './context/AuthContext'
import BookingPage from './pages/BookingPage'
import DashboardPage from './pages/DashboardPage'
import DoctorPage from './pages/DoctorPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import SignupPage from './pages/SignupPage'
import ManagementPage from './pages/ManagementPage'
import VoiceAgentPage from './pages/VoiceAgentPage'

function HomeRedirect() {
  const { user } = useAuth()
  const homes = {
    DOCTOR: '/doctor',
    HOSPITAL_MANAGER: '/manager',
    SUPERADMIN: '/admin',
    PATIENT: '/dashboard',
  }
  return <Navigate to={user ? homes[user.role] || '/dashboard' : '/login'} replace />
}

function AppFrame() {
  const location = useLocation()
  const { user } = useAuth()
  const authScreen = location.pathname === '/login' || location.pathname === '/signup'
  const authenticatedApp = Boolean(user && !authScreen)
  return <>{authenticatedApp && <Sidebar />}<div className={authenticatedApp ? 'app-stage' : ''}>{!authScreen && user && <Navbar />}<Routes>
    <Route path="/" element={<HomeRedirect />} />
    <Route path="/login" element={<LoginPage />} />
    <Route path="/signup" element={<SignupPage />} />
    <Route element={<ProtectedRoute allowRole="PATIENT" />}><Route path="/dashboard" element={<DashboardPage />} /><Route path="/book" element={<BookingPage />} /></Route>
    <Route element={<ProtectedRoute allowRole="DOCTOR" />}><Route path="/doctor" element={<DoctorPage />} /></Route>
    <Route element={<ProtectedRoute allowRoles={['PATIENT', 'DOCTOR']} />}><Route path="/voice" element={<VoiceAgentPage />} /></Route>
    <Route element={<ProtectedRoute allowRoles={['HOSPITAL_MANAGER', 'SUPERADMIN']} />}><Route path="/manager" element={<ManagementPage />} /></Route>
    <Route element={<ProtectedRoute allowRole="SUPERADMIN" />}><Route path="/admin" element={<ManagementPage superadmin />} /></Route>
    <Route path="*" element={<NotFoundPage />} />
  </Routes>{authenticatedApp && location.pathname !== '/voice' && ['DOCTOR', 'PATIENT'].includes(user.role) && <AssistantPanel />}</div></>
}

export default AppFrame
