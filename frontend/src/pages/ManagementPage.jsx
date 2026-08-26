import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import StatCard from '../components/StatCard'
import { useAuth } from '../context/AuthContext'

const emptyForm = {
  first_name: '', last_name: '', email: '', mobile_number: '+91', password: '', role: 'DOCTOR', qualification: '', specialty: '', consultation_hours: '10:00 - 13:00, 17:00 - 20:00',
}

function titleFor(role) {
  if (role === 'SUPERADMIN') return 'Superadmin control room'
  return 'Hospital management'
}

function labelFor(role) { return role.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase()) }

export default function ManagementPage({ superadmin = false }) {
  const { user } = useAuth()
  const [overview, setOverview] = useState(null)
  const [doctors, setDoctors] = useState([])
  const [patients, setPatients] = useState([])
  const [managers, setManagers] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const canManageManagers = superadmin && user.role === 'SUPERADMIN'

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const requests = [
        api.get('/api/v1/management/overview', { auth: true }),
        api.get('/api/v1/management/users?role=DOCTOR', { auth: true }),
        api.get('/api/v1/management/users?role=PATIENT', { auth: true }),
      ]
      if (canManageManagers) requests.push(api.get('/api/v1/management/users?role=HOSPITAL_MANAGER', { auth: true }))
      const [overviewData, doctorData, patientData, managerData = []] = await Promise.all(requests)
      setOverview(overviewData); setDoctors(doctorData); setPatients(patientData); setManagers(managerData)
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Unable to load hospital operations.')
    } finally { setLoading(false) }
  }, [canManageManagers])

  useEffect(() => { load() }, [load])

  const visibleRoles = useMemo(() => canManageManagers ? ['DOCTOR', 'PATIENT', 'HOSPITAL_MANAGER'] : ['DOCTOR', 'PATIENT'], [canManageManagers])
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }))
  const createAccount = async (event) => {
    event.preventDefault()
    setSaving(true); setError(''); setNotice('')
    try {
      const payload = { ...form, qualification: form.role === 'DOCTOR' ? form.qualification : null, specialty: form.role === 'DOCTOR' ? form.specialty : null, consultation_hours: form.role === 'DOCTOR' ? form.consultation_hours : null }
      const created = await api.post('/api/v1/management/users', payload, { auth: true })
      setNotice(`${labelFor(created.role)} account created for ${created.name}.`)
      setForm({ ...emptyForm, role: form.role })
      await load()
    } catch (requestError) { setError(requestError instanceof ApiError ? requestError.message : 'Unable to create that account.') } finally { setSaving(false) }
  }
  const changeStatus = async (account) => {
    const action = account.is_active ? 'deactivate' : 'restore'
    if (!window.confirm(`${action[0].toUpperCase()}${action.slice(1)} ${account.name}'s account?`)) return
    setError(''); setNotice('')
    try {
      await api.post(`/api/v1/management/users/${account.id}/status`, { is_active: !account.is_active }, { auth: true })
      setNotice(`${account.name}'s account was ${account.is_active ? 'deactivated' : 'restored'}.`)
      await load()
    } catch (requestError) { setError(requestError instanceof ApiError ? requestError.message : 'Unable to update account status.') }
  }

  return <main className="page-shell page-section"><section className="hero-grid hero-enter"><div><p className="eyebrow">{superadmin ? 'CityCare system' : 'Single-hospital workspace'}</p><h1 className="display-title">{titleFor(user.role)}.</h1><p className="mt-3 max-w-2xl text-slate-600">Manage the CityCare team, patient access, and clinic flow from one controlled workspace. This instance intentionally contains one hospital; it is not pretending to be a half-built multi-tenant SaaS.</p></div><div className="manager-lockup"><span>CityCare</span><strong>{overview?.hospital?.city || 'Nagpur'}</strong></div></section>
    <ErrorBanner message={error} onDismiss={() => setError('')} />{notice && <div className="notice-banner" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss notice">×</button></div>}
    <section className="grid gap-4 md:grid-cols-3">{loading ? <><div className="skeleton h-36" /><div className="skeleton h-36" /><div className="skeleton h-36" /></> : <><StatCard label="Active patients" value={overview?.active_patients} detail="Patient accounts with access" /><StatCard label="Active doctors" value={overview?.active_doctors} detail="Care-team accounts" accent="aqua" /><StatCard label="Visits ahead" value={overview?.upcoming_visits} detail={`${overview?.todays_visits ?? 0} scheduled today`} accent="ink" /></>}</section>
    <section id="team" className="management-grid reveal-card"><article className="management-form-card"><p className="eyebrow">Provision access</p><h2 className="section-title">Add a CityCare account</h2><p className="mt-2 text-sm leading-6 text-slate-600">Public signup only creates patients. Use this controlled form for staff-created patients, doctors, and—only for the superadmin—managers.</p><form className="mt-6 grid gap-4" onSubmit={createAccount}><label><span>Account role</span><select className="field-input mt-2" value={form.role} onChange={(event) => update('role', event.target.value)}>{visibleRoles.map((role) => <option key={role} value={role}>{labelFor(role)}</option>)}</select></label><div className="grid gap-4 sm:grid-cols-2"><label><span>First name</span><input className="field-input mt-2" required value={form.first_name} onChange={(event) => update('first_name', event.target.value)} /></label><label><span>Last name</span><input className="field-input mt-2" required value={form.last_name} onChange={(event) => update('last_name', event.target.value)} /></label></div><label><span>Work email</span><input className="field-input mt-2" type="email" required value={form.email} onChange={(event) => update('email', event.target.value)} /></label><div className="grid gap-4 sm:grid-cols-2"><label><span>Mobile (+91)</span><input className="field-input mt-2" required value={form.mobile_number} onChange={(event) => update('mobile_number', event.target.value)} /></label><label><span>Temporary password</span><input className="field-input mt-2" type="password" minLength="8" required value={form.password} onChange={(event) => update('password', event.target.value)} /></label></div>{form.role === 'DOCTOR' && <div className="doctor-fields"><label><span>Qualification</span><input className="field-input mt-2" required value={form.qualification} onChange={(event) => update('qualification', event.target.value)} placeholder="e.g. MBBS, MD" /></label><label><span>Specialty</span><input className="field-input mt-2" required value={form.specialty} onChange={(event) => update('specialty', event.target.value)} placeholder="e.g. General Medicine" /></label><label><span>Consultation hours</span><input className="field-input mt-2" value={form.consultation_hours} onChange={(event) => update('consultation_hours', event.target.value)} /></label></div>}<button className="button-primary w-full" disabled={saving}>{saving ? 'Creating account...' : `Create ${labelFor(form.role)}`}</button></form></article>
      <aside className="management-guidance"><p className="eyebrow">Access controls</p><h2>Simple hierarchy. Actual restrictions.</h2><div className="role-ladder"><div><strong>Superadmin</strong><span>Full CityCare control and manager provisioning</span></div><div><strong>Hospital manager</strong><span>Creates doctors and patients; manages their access</span></div><div><strong>Doctor</strong><span>Own schedule, care signals, staff-only Compass</span></div><div><strong>Patient</strong><span>Own bookings and selected physician only</span></div></div><p className="mt-6 text-sm leading-6 text-slate-600">Account deactivation is a reversible soft delete. Appointments stay in the clinical record, so no one destroys booking history by deleting a person.</p></aside></section>
    <AccountTable id="patients" title="Patients" subtitle="Registered patient accounts" accounts={patients} onStatus={changeStatus} loading={loading} />
    <AccountTable id="bookings" title="Doctors" subtitle="Care-team accounts and appointment availability" accounts={doctors} onStatus={changeStatus} loading={loading} showClinical />
    {canManageManagers && <AccountTable title="Hospital managers" subtitle="Administrative accounts" accounts={managers} onStatus={changeStatus} loading={loading} />}
  </main>
}

function AccountTable({ id, title, subtitle, accounts, onStatus, loading, showClinical = false }) {
  return <section id={id} className="mt-12 scroll-mt-24"><div className="mb-5 flex items-end justify-between gap-4"><div><p className="eyebrow">{subtitle}</p><h2 className="section-title">{title}</h2></div><span className="text-sm font-bold text-slate-500">{accounts.length} total</span></div>{loading ? <div className="skeleton h-60" /> : accounts.length ? <div className="account-table-wrap"><div className="overflow-x-auto"><table><thead><tr><th>Name</th><th>Contact</th>{showClinical && <><th>Specialty</th><th>Hours</th></>}<th>Access</th><th /></tr></thead><tbody>{accounts.map((account) => <tr key={account.id}><td><strong>{account.name}</strong><small>{account.email}</small></td><td>{account.mobile_number}</td>{showClinical && <><td>{account.specialty || '-'}</td><td>{account.consultation_hours || '-'}</td></>}<td><span className={`status-badge ${account.is_active ? 'status-booked' : 'status-cancelled'}`}>{account.is_active ? 'Active' : 'Inactive'}</span></td><td><button type="button" onClick={() => onStatus(account)} className="account-action">{account.is_active ? 'Deactivate' : 'Restore'}</button></td></tr>)}</tbody></table></div></div> : <div className="empty-state"><span>○</span><p>No {title.toLowerCase()} yet.</p><span>Create an account above to add it to CityCare.</span></div>}</section>
}
