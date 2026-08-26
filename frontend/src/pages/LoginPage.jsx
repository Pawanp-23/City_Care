import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import FormInput from '../components/FormInput'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { signIn } = useAuth()
  const [form, setForm] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    const nextErrors = {}
    if (!/^\S+@\S+\.\S+$/.test(form.email)) nextErrors.email = 'Enter a valid email address.'
    if (!form.password) nextErrors.password = 'Password is required.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return

    setLoading(true)
    setServerError('')
    try {
      const session = await api.post('/api/v1/auth/login', form)
      signIn(session)
      const home = session.user.role === 'DOCTOR' ? '/doctor' : '/dashboard'
      const from = location.state?.from?.pathname
      navigate(from && !from.startsWith('/doctor') ? from : home, { replace: true })
    } catch (error) {
      setServerError(error instanceof ApiError ? error.message : 'Unable to sign in right now.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-orb auth-orb-one" /><div className="auth-orb auth-orb-two" />
      <section className="auth-panel">
        <div className="auth-aside">
          <span className="brand-mark">+</span>
          <p className="eyebrow text-teal-100">CityCare Clinic · Nagpur</p>
          <h1>Care that starts before you arrive.</h1>
          <p>Book a clear, conflict-free consultation with Dr. Pawan Patil, General Physician.</p>
          <div className="auth-feature"><span>◷</span><div><strong>12 focused slots</strong><small>Morning and evening consultation hours</small></div></div>
          <div className="auth-feature"><span>⌁</span><div><strong>Private by design</strong><small>Your appointments stay yours</small></div></div>
        </div>
        <div className="auth-form-wrap">
          <div className="mb-8"><p className="eyebrow">Welcome back</p><h2>Sign in to CityCare</h2><p className="mt-2 text-sm text-slate-500">Use the account you created to manage your appointments.</p></div>
          <ErrorBanner message={serverError} onDismiss={() => setServerError('')} />
          <form noValidate onSubmit={submit} className="space-y-5">
            <FormInput label="Email address" id="login-email" type="email" autoComplete="email" placeholder="you@example.com" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} error={errors.email} />
            <FormInput label="Password" id="login-password" type="password" autoComplete="current-password" placeholder="Your password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} error={errors.password} />
            <button className="button-primary w-full" disabled={loading}>{loading ? 'Signing you in…' : 'Sign in securely'}</button>
          </form>
          <p className="mt-7 text-center text-sm text-slate-600">New to CityCare? <Link className="font-bold text-brand hover:underline" to="/signup">Create your account</Link></p>
        </div>
      </section>
    </main>
  )
}
