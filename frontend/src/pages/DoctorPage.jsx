import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import ScheduleTable from '../components/ScheduleTable'
import StatCard from '../components/StatCard'
import { useAuth } from '../context/AuthContext'
import { formatDate, plusDaysISO, todayISO } from '../utils/date'

function nextScheduledAppointment(schedule, selectedDate) {
  if (selectedDate < todayISO()) return null
  if (selectedDate > todayISO()) return schedule[0] ?? null
  const currentTime = new Date().toTimeString().slice(0, 5)
  return schedule.find((appointment) => appointment.slot >= currentTime) ?? null
}

export default function DoctorPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [schedule, setSchedule] = useState([])
  const [availableSlots, setAvailableSlots] = useState(null)
  const [selectedDate, setSelectedDate] = useState(todayISO)
  const [query, setQuery] = useState('')
  const [onlyClinicalSignals, setOnlyClinicalSignals] = useState(false)
  const [loadingStats, setLoadingStats] = useState(true)
  const [loadingSchedule, setLoadingSchedule] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ diagnosis: '', medicines: '', instructions: '' })
  const [saving, setSaving] = useState(false)
  const [issued, setIssued] = useState(null)
  const [attachmentStatus, setAttachmentStatus] = useState('')

  const handleError = useCallback((requestError) => {
    if (requestError instanceof ApiError && requestError.status === 403) {
      navigate('/dashboard', { replace: true })
      return
    }
    setError(requestError instanceof ApiError ? requestError.message : 'Unable to load doctor dashboard.')
  }, [navigate])

  const loadStats = useCallback(async () => {
    setLoadingStats(true)
    try { setStats(await api.get('/api/v1/doctor/stats', { auth: true })) } catch (requestError) { handleError(requestError) } finally { setLoadingStats(false) }
  }, [handleError])

  const loadSchedule = useCallback(async (date) => {
    setLoadingSchedule(true)
    setAvailableSlots(null)
    try {
      const data = await api.get(`/api/v1/doctor/schedule?date=${date}`, { auth: true })
      setSchedule(data.appointments)
      if (date >= todayISO() && date <= plusDaysISO(7)) {
        try {
          const availability = await api.get(`/api/v1/appointments/free-slots?date=${date}&doctor_id=${user.id}`)
          setAvailableSlots(availability.slots)
        } catch {
          setAvailableSlots(null)
        }
      }
    } catch (requestError) {
      setSchedule([])
      handleError(requestError)
    } finally {
      setLoadingSchedule(false)
    }
  }, [handleError, user?.id])

  useEffect(() => { loadStats() }, [loadStats])
  useEffect(() => { loadSchedule(selectedDate) }, [selectedDate, loadSchedule])

  const filteredSchedule = useMemo(() => schedule.filter((appointment) => {
    const matchesText = `${appointment.patient_name} ${appointment.reason} ${appointment.symptoms?.join(' ')}`.toLowerCase().includes(query.trim().toLowerCase())
    const hasSignal = Boolean(appointment.temperature_f || appointment.symptoms?.length)
    return matchesText && (!onlyClinicalSignals || hasSignal)
  }), [schedule, query, onlyClinicalSignals])
  const nextAppointment = useMemo(() => nextScheduledAppointment(schedule, selectedDate), [schedule, selectedDate])
  const totalCapacity = availableSlots === null ? null : schedule.length + availableSlots.length
  const capacityPercent = totalCapacity ? Math.round((schedule.length / totalCapacity) * 100) : 0
  const accept = async (appointment) => {
    try {
      await api.post(`/api/v1/doctor/appointments/${appointment.id}/accept`, undefined, { auth: true })
      await loadSchedule(selectedDate)
    } catch (e) {
      handleError(e)
    }
  }
  const startPrescription = (appointment) => {
    setError('')
    setIssued(null)
    setAttachmentStatus('')
    setEditing(appointment)
  }
  const prescribe = async () => {
    if (!editing) return
    const medicines = form.medicines.split('\n').map((item) => item.trim()).filter(Boolean)
    setSaving(true)
    try {
      const prescription = await api.post(`/api/v1/doctor/appointments/${editing.id}/prescriptions`, {
        diagnosis: form.diagnosis.trim(),
        medicines,
        instructions: form.instructions.trim(),
      }, { auth: true })
      setIssued(prescription)
      setEditing(null)
      setForm({ diagnosis: '', medicines: '', instructions: '' })
      await loadSchedule(selectedDate)
    } catch (e) {
      handleError(e)
    } finally {
      setSaving(false)
    }
  }
  const attach = async (file) => {
    if (!file || !issued) return
    setAttachmentStatus('Indexing document for the patient assistant...')
    try {
      setIssued(await api.upload(`/api/v1/doctor/prescriptions/${issued.id}/attachments`, file, { auth: true }))
      setAttachmentStatus('Document indexed. The patient assistant can now retrieve it.')
    } catch (e) {
      setAttachmentStatus('')
      handleError(e)
    }
  }
  const openIssuedPdf = async () => {
    if (!issued?.id) return
    try {
      const result = await api.download(`/api/v1/prescriptions/${issued.id}/download`)
      window.open(result.url, '_blank', 'noopener,noreferrer')
    } catch (e) {
      handleError(e)
    }
  }

  return <main className="page-shell page-section"><section className="hero-grid hero-enter"><div><p className="eyebrow">Doctor dashboard</p><h1 className="display-title">Run the day with less friction.</h1><p className="mt-3 max-w-2xl text-slate-600">Live appointments, useful care signals, and a clear view of the clinic load - all from real booking data.</p></div><div className="schedule-date-chip"><span className="block text-xs font-bold uppercase tracking-widest text-teal-200">Schedule viewing</span><strong className="mt-1 block">{formatDate(selectedDate)}</strong></div></section><ErrorBanner message={error} onDismiss={() => setError('')} />
    <section className="grid gap-4 md:grid-cols-3">{loadingStats ? <><div className="skeleton h-36" /><div className="skeleton h-36" /><div className="skeleton h-36" /></> : <><StatCard label="Registered patients" value={stats?.total_registered_patients} detail="Active patient accounts" /><StatCard label="Today's visits" value={stats?.todays_visits} detail="Booked consultations today" accent="aqua" /><StatCard label="Upcoming visits" value={stats?.upcoming_visits} detail="Today and later" accent="ink" /></>}</section>
    <section className="doctor-signal-grid reveal-card"><article className="next-patient-panel"><p className="eyebrow">Up next</p>{nextAppointment ? <><h2>{nextAppointment.patient_name}</h2><p className="mt-1 font-bold text-brand">{nextAppointment.slot} consultation</p><p className="mt-4 text-sm leading-6 text-slate-600">{nextAppointment.reason}</p><div className="mt-4 flex flex-wrap gap-2">{nextAppointment.temperature_f && <span className="signal-pill signal-warm">{nextAppointment.temperature_f} F</span>}{nextAppointment.symptoms?.map((symptom) => <span className="signal-pill" key={symptom}>{symptom}</span>)}</div></> : <><h2>{selectedDate === todayISO() ? 'No more visits today.' : 'No appointment selected.'}</h2><p className="mt-3 text-sm leading-6 text-slate-600">The schedule is clear for this view. Choose another date to review future visits.</p></>}</article>
      <article className="capacity-panel"><div className="flex items-start justify-between gap-4"><div><p className="eyebrow">Clinic capacity</p><h2>{totalCapacity === null ? 'Availability unavailable' : `${schedule.length} of ${totalCapacity} slots filled`}</h2></div><span className="capacity-value">{totalCapacity === null ? '-' : `${capacityPercent}%`}</span></div><div className="capacity-track" aria-label={totalCapacity === null ? 'Capacity is unavailable for this date' : `${capacityPercent}% schedule capacity used`}><span style={{ width: `${capacityPercent}%` }} /></div><p className="mt-4 text-sm text-slate-600">{availableSlots === null ? 'Live slot capacity is available for dates in the booking window.' : `${availableSlots.length} live appointment slots remain for this day.`}</p></article>
    </section>
    <section id="schedule" className="mt-11 scroll-mt-24"><div className="mb-5 flex flex-col justify-between gap-4 lg:flex-row lg:items-end"><div><p className="eyebrow">Daily schedule</p><h2 className="section-title">Appointments for the day</h2></div><div className="flex flex-col gap-3 sm:flex-row sm:items-end"><label className="text-sm font-semibold text-slate-700">View date<input className="field-input mt-2 min-w-48" type="date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} /></label><label className="text-sm font-semibold text-slate-700">Find a patient or reason<input className="field-input mt-2 min-w-52" type="search" placeholder="Search today's list" value={query} onChange={(event) => setQuery(event.target.value)} /></label></div></div><div className="mb-4 flex flex-wrap items-center gap-3"><button type="button" onClick={() => setOnlyClinicalSignals((value) => !value)} className={`filter-chip ${onlyClinicalSignals ? 'filter-chip-active' : ''}`}> {onlyClinicalSignals ? 'Showing clinical signals' : 'Show clinical signals only'} </button><span className="text-sm font-semibold text-slate-500">{filteredSchedule.length} of {schedule.length} visits visible</span></div>{loadingSchedule ? <div className="skeleton h-64" /> : <ScheduleTable schedule={filteredSchedule} date={selectedDate} isFiltered={Boolean(query || onlyClinicalSignals)} onAccept={accept} onPrescribe={(appointment) => setEditing(appointment)} />}</section>
    {editing && <section className="reveal-card mt-8 max-w-2xl border border-teal-100 p-6"><p className="eyebrow">Prescription for {editing.patient_name}</p><h2 className="section-title">Issue a PDF prescription</h2><label className="mt-4 block text-sm font-bold">Diagnosis<input className="field-input mt-1" value={form.diagnosis} onChange={(e) => setForm({ ...form, diagnosis: e.target.value })} /></label><label className="mt-3 block text-sm font-bold">Medicines (one per line)<textarea className="field-input mt-1" rows="4" value={form.medicines} onChange={(e) => setForm({ ...form, medicines: e.target.value })} /></label><label className="mt-3 block text-sm font-bold">Instructions<textarea className="field-input mt-1" rows="4" value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} /></label><div className="mt-4 flex gap-3"><button className="button-primary" onClick={prescribe} disabled={saving || !form.diagnosis || !form.instructions}>{saving ? 'Creating…' : 'Create & store PDF'}</button><button className="text-sm font-bold" onClick={() => setEditing(null)}>Cancel</button></div></section>}
    {issued && <section className="reveal-card mt-6 max-w-2xl border border-teal-100 p-6"><p className="eyebrow">Prescription stored</p><h2 className="section-title">Add a readable supporting document</h2><p className="mt-2 text-sm text-slate-600">PDF, TXT, MD, or CSV up to 10 MB. Its text is indexed only for this patient’s assistant.</p>{issued.storage === 'local' && <p className="mt-2 text-xs font-semibold text-amber-700">Stored locally for development. Configure Cloudinary before any real deployment.</p>}<input className="mt-4 block text-sm" type="file" accept=".pdf,.txt,.md,.csv" onChange={(e) => attach(e.target.files?.[0])} /><button type="button" className="mt-4 block text-sm font-bold text-brand underline" onClick={openIssuedPdf}>Open stored prescription PDF</button></section>}
  </main>
}
