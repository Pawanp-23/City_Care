import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import FormInput from '../components/FormInput'
import { useAuth } from '../context/AuthContext'

const initialForm = { first_name: '', last_name: '', email: '', mobile_number: '+91', password: '', confirmPassword: '' }

export default function SignupPage() {
  const navigate = useNavigate()
  const { signIn } = useAuth()
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [loading, setLoading] = useState(false)

  const change = (event) => setForm({ ...form, [event.target.name]: event.target.value })
  const submit = async (event) => {
    event.preventDefault()
    const nextErrors = {}
    if (!form.first_name.trim()) nextErrors.first_name = 'First name is required.'
    if (!form.last_name.trim()) nextErrors.last_name = 'Last name is required.'
    if (!/^\S+@\S+\.\S+$/.test(form.email)) nextErrors.email = 'Enter a valid email address.'
    if (!/^\+91[6-9]\d{9}$/.test(form.mobile_number.replace(/[ -]/g, ''))) nextErrors.mobile_number = 'Use +91 followed by a 10-digit Indian mobile number.'
    if (form.password.length < 8) nextErrors.password = 'Use at least 8 characters.'
    if (!/[A-Z]/.test(form.password) || !/[a-z]/.test(form.password) || !/\d/.test(form.password)) nextErrors.password = 'Use upper- and lowercase letters plus a number.'
    if (form.password !== form.confirmPassword) nextErrors.confirmPassword = 'Passwords do not match.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length) return

    setLoading(true)
    setServerError('')
    try {
      const { confirmPassword, ...payload } = form
      const session = await api.post('/api/v1/auth/signup', { ...payload, mobile_number: payload.mobile_number.replace(/[ -]/g, '') })
      signIn(session)
      navigate('/dashboard', { replace: true })
    } catch (error) {
      setServerError(error instanceof ApiError ? error.message : 'Unable to create your account right now.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page py-6">
      <div className="auth-orb auth-orb-one" /><div className="auth-orb auth-orb-two" />
      <section className="auth-panel auth-panel-signup">
        <div className="auth-aside"><span className="brand-mark">+</span><p className="eyebrow text-teal-100">CityCare Clinic · Nagpur</p><h1>A calmer way to see your doctor.</h1><p>Choose a free slot, share what is going on, and arrive knowing your time is reserved.</p><div className="mt-auto rounded-2xl border border-white/15 bg-white/10 p-5 text-sm text-teal-50">Your account is always created as a patient. Doctor access is never available through public signup.</div></div>
        <div className="auth-form-wrap">
          <div className="mb-7"><p className="eyebrow">Create account</p><h2>Join CityCare</h2><p className="mt-2 text-sm text-slate-500">It takes less than a minute to set up your patient account.</p></div>
          <ErrorBanner message={serverError} onDismiss={() => setServerError('')} />
          <form noValidate onSubmit={submit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2"><FormInput label="First name" id="first-name" name="first_name" autoComplete="given-name" value={form.first_name} onChange={change} error={errors.first_name} /><FormInput label="Last name" id="last-name" name="last_name" autoComplete="family-name" value={form.last_name} onChange={change} error={errors.last_name} /></div>
            <FormInput label="Email address" id="signup-email" name="email" type="email" autoComplete="email" placeholder="you@example.com" value={form.email} onChange={change} error={errors.email} />
            <FormInput label="Mobile number" id="mobile" name="mobile_number" type="tel" autoComplete="tel" placeholder="+919876543210" value={form.mobile_number} onChange={change} error={errors.mobile_number} />
            <div className="grid gap-4 sm:grid-cols-2"><FormInput label="Password" id="signup-password" name="password" type="password" autoComplete="new-password" value={form.password} onChange={change} error={errors.password} /><FormInput label="Confirm password" id="confirm-password" name="confirmPassword" type="password" autoComplete="new-password" value={form.confirmPassword} onChange={change} error={errors.confirmPassword} /></div>
            <button className="button-primary w-full" disabled={loading}>{loading ? 'Creating your account…' : 'Create patient account'}</button>
          </form>
          <p className="mt-6 text-center text-sm text-slate-600">Already registered? <Link className="font-bold text-brand hover:underline" to="/login">Sign in</Link></p>
        </div>
      </section>
    </main>
  )
}
