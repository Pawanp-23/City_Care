import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import AppointmentCard from '../components/AppointmentCard'
import ErrorBanner from '../components/ErrorBanner'
import { useAuth } from '../context/AuthContext'
import { useTilt } from '../hooks/useTilt'
import { formatDate, todayISO } from '../utils/date'

function sortSoonest(items) {
  return [...items].sort((first, second) => `${first.appointment_date}T${first.slot}`.localeCompare(`${second.appointment_date}T${second.slot}`))
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [clinic, setClinic] = useState(null)
  const [doctors, setDoctors] = useState([])
  const [appointments, setAppointments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cancellingId, setCancellingId] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [clinicData, appointmentData, doctorData] = await Promise.all([
        api.get('/api/v1/clinic'),
        api.get('/api/v1/appointments/mine', { auth: true }),
        api.get('/api/v1/doctors'),
      ])
      setClinic(clinicData)
      setAppointments(appointmentData)
      setDoctors(doctorData)
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Unable to load your dashboard.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const nextAppointment = useMemo(() => sortSoonest(appointments.filter((appointment) => ['PENDING', 'ACCEPTED', 'BOOKED'].includes(appointment.status) && appointment.appointment_date >= todayISO()))[0], [appointments])
  const activeAppointments = useMemo(() => appointments.filter((appointment) => ['PENDING', 'ACCEPTED', 'BOOKED'].includes(appointment.status)).length, [appointments])

  const cancel = async (appointment) => {
    if (!window.confirm(`Cancel your ${appointment.slot} appointment on ${appointment.appointment_date}?`)) return
    setCancellingId(appointment.id)
    setError('')
    try {
      const updated = await api.post(`/api/v1/appointments/${appointment.id}/cancel`, undefined, { auth: true })
      setAppointments((items) => items.map((item) => item.id === updated.id ? updated : item))
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Unable to cancel your appointment.')
    } finally {
      setCancellingId('')
    }
  }

  const tilt = useTilt()
  return (
    <main className="page-shell page-section">
      <section className="hero-grid hero-enter">
        <div><p className="eyebrow">Patient dashboard</p><h1 className="display-title">Good to see you, {user.first_name}.</h1><p className="mt-3 max-w-xl text-slate-600">Your appointments, live clinic availability, and the little details that make a visit easier.</p></div>
        <Link to="/book" className="button-primary button-pulse self-center justify-self-start sm:justify-self-end">Book appointment <span aria-hidden>→</span></Link>
      </section>
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      {loading ? <div className="grid gap-6 lg:grid-cols-[1.25fr_.75fr]"><div className="skeleton h-64" /><div className="skeleton h-64" /></div> : (
        <div className="grid gap-7 lg:grid-cols-[1.15fr_.85fr]">
          <section ref={tilt.ref} onMouseMove={tilt.onMouseMove} onMouseLeave={tilt.onMouseLeave} className="tilt-card clinic-card reveal-card">
            <div className="clinic-glow" /><p className="eyebrow text-teal-100">Your physician</p>
            <h2>{clinic?.doctor_name ?? 'CityCare Clinic'}</h2><p className="mt-2 font-medium text-teal-50">{clinic?.qualification} · {clinic?.specialty}</p>
            <p className="mt-8 text-sm text-teal-100">{clinic?.clinic_name} · {clinic?.city}</p>
            <div className="mt-4 grid gap-3 border-t border-white/15 pt-5 text-sm sm:grid-cols-2"><div><span className="block text-xs uppercase tracking-wider text-teal-200">Morning</span><strong>{clinic?.morning_hours}</strong></div><div><span className="block text-xs uppercase tracking-wider text-teal-200">Evening</span><strong>{clinic?.evening_hours}</strong></div></div>
          </section>
          <aside className="next-visit-card reveal-card" aria-live="polite">
            {nextAppointment ? <><div className="flex items-start justify-between gap-4"><div><p className="eyebrow">Your next visit</p><h2 className="mt-2 text-2xl font-black tracking-tight text-ink">{formatDate(nextAppointment.appointment_date)}</h2><p className="mt-1 text-sm font-bold text-brand">{nextAppointment.slot} with Dr. Pawan Patil</p></div><span className="date-orb">{nextAppointment.appointment_date.slice(-2)}</span></div><p className="mt-5 text-sm leading-6 text-slate-600">{nextAppointment.reason}</p><div className="mt-5 flex items-center justify-between border-t border-teal-100 pt-4"><span className="text-xs font-semibold text-slate-500">{nextAppointment.symptoms?.length ? nextAppointment.symptoms.join(' · ') : 'Consultation booked'}</span><a className="text-sm font-bold text-brand hover:underline" href="#appointments">View visit</a></div></> : <><p className="eyebrow">Care starts here</p><h2 className="mt-2 text-2xl font-black tracking-tight text-ink">No visit booked yet.</h2><p className="mt-3 text-sm leading-6 text-slate-600">See live times and reserve the slot that works for you. There is no waiting-list guesswork.</p><Link to="/book" className="mt-6 inline-flex text-sm font-bold text-brand hover:underline">Choose a time →</Link></>}
          </aside>
        </div>
      )}

      <section className="patient-insights reveal-card"><div className="insight-icon">✓</div><div><p className="text-sm font-black text-ink">A smoother appointment starts at home.</p><p className="mt-1 text-sm leading-6 text-slate-600">Bring your current medicines, note your temperature if relevant, and keep any recent reports handy. Your saved reason and symptoms are already visible to the clinic.</p></div><div className="insight-metric"><strong>{activeAppointments}</strong><span>active booking{activeAppointments === 1 ? '' : 's'}</span></div></section>

      <TelegramConnectCard />

      <section id="appointments" className="mt-12 scroll-mt-24"><div className="mb-5 flex items-end justify-between gap-4"><div><p className="eyebrow">My appointments</p><h2 className="section-title">Your care schedule</h2></div><span className="text-sm font-semibold text-slate-500">{appointments.length} total</span></div>
        {loading ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"><div className="skeleton h-48" /><div className="skeleton h-48" /></div> : appointments.length ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{sortSoonest(appointments).map((appointment, index) => <div key={appointment.id} style={{ animationDelay: `${index * 70}ms` }}><AppointmentCard appointment={appointment} onCancel={cancel} cancelling={cancellingId === appointment.id} /></div>)}</div> : <div className="empty-state"><span className="text-3xl">✦</span><p>No appointments yet.</p><span>Choose a convenient time with Dr. Pawan Patil.</span><Link className="button-primary mt-5" to="/book">Book your first visit</Link></div>}
      </section>
      <PrescriptionList />
    </main>
  )
}

function TelegramConnectCard() {
  const [link, setLink] = useState(null)
  const [status, setStatus] = useState(null)
  const [checking, setChecking] = useState(true)
  const [creating, setCreating] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')
  const botUsername = (import.meta.env.VITE_TELEGRAM_BOT_USERNAME || '').replace(/^@/, '')

  const checkStatus = useCallback(async () => {
    setChecking(true)
    setError('')
    try {
      const nextStatus = await api.get('/api/v1/integrations/telegram/link-status', { auth: true })
      setStatus(nextStatus)
      if (nextStatus.linked) setLink(null)
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Unable to check Telegram connection status.')
    } finally {
      setChecking(false)
    }
  }, [])

  useEffect(() => { checkStatus() }, [checkStatus])

  const createCode = async () => {
    setCreating(true)
    setCopied(false)
    setError('')
    try {
      setLink(await api.post('/api/v1/integrations/telegram/link-code', undefined, { auth: true }))
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Unable to create a Telegram link code.')
    } finally {
      setCreating(false)
    }
  }

  const copyCommand = async () => {
    if (!link?.command) return
    try {
      await navigator.clipboard.writeText(link.command)
      setCopied(true)
    } catch {
      setError('Copy was blocked by the browser. Select the command and copy it manually.')
    }
  }

  const telegramUrl = link && botUsername
    ? `https://t.me/${botUsername}?start=link_${encodeURIComponent(link.code)}`
    : ''

  return (
    <section className="reveal-card mt-7 rounded-2xl border border-sky-100 bg-white/90 p-6 shadow-lg shadow-slate-900/5">
      <div className="grid gap-5 lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <p className="eyebrow">Telegram patient assistant</p>
          <h2 className="mt-2 text-xl font-black text-ink">Connect your existing patient account</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Generate a one-time code, then open the Medihub bot. The code expires after 10 minutes and can be used only once.</p>
        </div>
        {status?.linked
          ? <span className="rounded-full bg-emerald-100 px-4 py-2 text-sm font-extrabold text-emerald-800">✓ Telegram connected</span>
          : !link && <button type="button" className="button-primary" onClick={createCode} disabled={creating || checking}>{checking ? 'Checking connection…' : creating ? 'Creating secure code…' : 'Connect Telegram'}</button>}
      </div>
      {error && <div className="mt-4"><ErrorBanner message={error} onDismiss={() => setError('')} /></div>}
      {status?.linked && (
        <div className="mt-5 rounded-xl border border-emerald-100 bg-emerald-50/70 p-4" aria-live="polite">
          <p className="font-extrabold text-emerald-900">Your patient account is securely connected{status.username ? ` to ${status.username}` : ''}.</p>
          <p className="mt-1 text-sm text-emerald-800">Appointments, doctor confirmation, and prescription notifications can now use Telegram.</p>
        </div>
      )}
      {link && !status?.linked && (
        <div className="mt-5 rounded-xl border border-teal-100 bg-teal-50/70 p-4" aria-live="polite">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">One-time Telegram command</p>
          <code className="mt-2 block break-all text-lg font-black text-ink">{link.command}</code>
          <p className="mt-2 text-xs text-slate-500">Expires {new Date(link.expires_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}. Do not share this code.</p>
          <div className="mt-4 flex flex-wrap gap-3">
            {telegramUrl && <a className="button-primary" href={telegramUrl} target="_blank" rel="noreferrer">Open Medihub bot</a>}
            <button type="button" className="rounded-xl border border-teal-200 bg-white px-4 py-3 text-sm font-extrabold text-brand" onClick={copyCommand}>{copied ? 'Copied' : 'Copy command'}</button>
            <button type="button" className="px-3 py-2 text-sm font-bold text-slate-600" onClick={createCode} disabled={creating}>Generate a new code</button>
            <button type="button" className="px-3 py-2 text-sm font-bold text-slate-600" onClick={checkStatus} disabled={checking}>{checking ? 'Checking…' : "I've linked it — check status"}</button>
          </div>
        </div>
      )}
    </section>
  )
}

function PrescriptionList() {
  const [items, setItems] = useState([])
  const [downloadError, setDownloadError] = useState('')
  useEffect(() => { api.get('/api/v1/prescriptions/mine', { auth: true }).then(setItems).catch(() => setItems([])) }, [])
  const download = async (item) => {
    try {
      const result = await api.download(`/api/v1/prescriptions/${item.id}/download`)
      window.open(result.url, '_blank', 'noopener,noreferrer')
    } catch (requestError) {
      setDownloadError(requestError instanceof ApiError ? requestError.message : 'Unable to open this prescription.')
    }
  }
  return <section className="mt-12"><p className="eyebrow">My prescriptions</p><h2 className="section-title">Documents from your doctor</h2>{downloadError && <ErrorBanner message={downloadError} onDismiss={() => setDownloadError('')} />}{items.length ? <div className="mt-4 grid gap-4 sm:grid-cols-2">{items.map((item) => <article className="appointment-card" key={item.id}><h3 className="font-black text-ink">{item.diagnosis}</h3><p className="mt-2 text-sm text-slate-600">{item.medicines.join(' · ') || 'No medicines listed'}</p><button type="button" className="button-primary mt-4" onClick={() => download(item)}>View / download PDF</button></article>)}</div> : <p className="mt-3 text-sm text-slate-500">Your issued prescriptions will appear here.</p>}</section>
}
