import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import SlotGrid from '../components/SlotGrid'
import { downloadAppointmentInvite } from '../utils/calendar'
import { formatDate, plusDaysISO, todayISO } from '../utils/date'

const symptomOptions = ['fever', 'cough', 'cold', 'bodyache', 'headache', 'other']

export default function BookingPage() {
  const [selectedDate, setSelectedDate] = useState(todayISO)
  const [doctors, setDoctors] = useState([])
  const [doctorId, setDoctorId] = useState('')
  const [slots, setSlots] = useState([])
  const [selectedSlot, setSelectedSlot] = useState('')
  const [reason, setReason] = useState('')
  const [temperature, setTemperature] = useState('')
  const [symptoms, setSymptoms] = useState([])
  const [loadingDoctors, setLoadingDoctors] = useState(true)
  const [loadingSlots, setLoadingSlots] = useState(false)
  const [slotError, setSlotError] = useState('')
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [confirmation, setConfirmation] = useState(null)

  const selectedDoctor = doctors.find((doctor) => doctor.id === doctorId)
  const loadDoctors = useCallback(async () => {
    setLoadingDoctors(true)
    try {
      const data = await api.get('/api/v1/doctors')
      setDoctors(data)
      setDoctorId((current) => current || data[0]?.id || '')
      if (!data.length) setSlotError('No doctor is currently available for online booking.')
    } catch (error) { setSlotError(error instanceof ApiError ? error.message : 'Unable to load the CityCare care team.') } finally { setLoadingDoctors(false) }
  }, [])
  const loadSlots = useCallback(async (date, providerId) => {
    if (!providerId) return
    setLoadingSlots(true); setSlotError('')
    try { const data = await api.get(`/api/v1/appointments/free-slots?date=${date}&doctor_id=${providerId}`); setSlots(data.slots) } catch (error) { setSlots([]); setSlotError(error instanceof ApiError ? error.message : 'Unable to load available times.') } finally { setLoadingSlots(false) }
  }, [])
  useEffect(() => { loadDoctors() }, [loadDoctors])
  useEffect(() => { setSelectedSlot(''); if (doctorId) loadSlots(selectedDate, doctorId) }, [selectedDate, doctorId, loadSlots])
  const toggleSymptom = (symptom) => setSymptoms((items) => items.includes(symptom) ? items.filter((item) => item !== symptom) : [...items, symptom])
  const submit = async (event) => {
    event.preventDefault()
    if (!doctorId) return setFormError('Choose a doctor before selecting a slot.')
    if (!selectedSlot) return setFormError('Choose an available appointment time.')
    if (reason.trim().length < 10) return setFormError('Please give a reason of at least 10 characters.')
    setSubmitting(true); setFormError('')
    try {
      const booking = await api.post('/api/v1/appointments', { doctor_id: doctorId, appointment_date: selectedDate, slot: selectedSlot, reason: reason.trim(), temperature_f: temperature === '' ? null : Number(temperature), symptoms }, { auth: true })
      setConfirmation({ ...booking, doctor_name: selectedDoctor?.name || 'your CityCare doctor' })
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) { setFormError('That slot just got booked - please pick another.'); setSelectedSlot(''); loadSlots(selectedDate, doctorId) } else { setFormError(error instanceof ApiError ? error.message : 'Unable to book your appointment.') }
    } finally { setSubmitting(false) }
  }
  if (confirmation) return <BookingConfirmation booking={confirmation} />
  return <main className="page-shell page-section max-w-5xl"><div className="mb-9"><Link className="text-sm font-bold text-brand hover:underline" to="/dashboard">Back to dashboard</Link><p className="mt-6 eyebrow">New appointment</p><h1 className="display-title">Reserve your consultation.</h1><p className="mt-2 max-w-2xl text-slate-600">Choose your CityCare physician, then see live availability for that clinician. A time is held only after your booking is confirmed.</p></div><form onSubmit={submit} className="grid gap-7 lg:grid-cols-[1fr_.82fr]" noValidate><section className="surface-card"><div className="step-label">1</div><h2 className="section-title">Choose doctor and time</h2><label className="mt-6 block"><span className="mb-2 block text-sm font-semibold text-slate-700">CityCare physician</span><select className="field-input" value={doctorId} onChange={(event) => setDoctorId(event.target.value)} disabled={loadingDoctors || !doctors.length}>{loadingDoctors ? <option>Loading care team...</option> : doctors.map((doctor) => <option key={doctor.id} value={doctor.id}>{doctor.name} - {doctor.specialty}</option>)}</select>{selectedDoctor && <span className="provider-caption">{selectedDoctor.qualification} · {selectedDoctor.consultation_hours}</span>}</label><label className="mt-5 block"><span className="mb-2 block text-sm font-semibold text-slate-700">Appointment date</span><input className="field-input" type="date" min={todayISO()} max={plusDaysISO(7)} value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} /></label><div className="mt-6"><p className="mb-3 text-sm font-semibold text-slate-700">Free slots for {formatDate(selectedDate)}</p><SlotGrid slots={slots} selectedSlot={selectedSlot} onSelect={setSelectedSlot} loading={loadingDoctors || loadingSlots} error={slotError} /></div></section><section className="surface-card"><div className="step-label">2</div><h2 className="section-title">Tell us what you need</h2><ErrorBanner message={formError} onDismiss={() => setFormError('')} /><label className="mt-6 block"><span className="mb-2 block text-sm font-semibold text-slate-700">Reason for visit <span className="text-rose-600">*</span></span><textarea className="field-input min-h-28 resize-y" minLength="10" maxLength="1000" placeholder="For example: recurring headache for the past two days" value={reason} onChange={(event) => setReason(event.target.value)} /></label><label className="mt-5 block"><span className="mb-2 block text-sm font-semibold text-slate-700">Temperature °F <span className="font-normal text-slate-400">(optional)</span></span><input className="field-input" type="number" min="95" max="110" step="0.1" placeholder="e.g. 98.6" value={temperature} onChange={(event) => setTemperature(event.target.value)} /></label><fieldset className="mt-5"><legend className="mb-3 text-sm font-semibold text-slate-700">Symptoms <span className="font-normal text-slate-400">(select any)</span></legend><div className="grid grid-cols-2 gap-2">{symptomOptions.map((symptom) => <label key={symptom} className={`symptom-option ${symptoms.includes(symptom) ? 'symptom-option-selected' : ''}`}><input className="sr-only" type="checkbox" checked={symptoms.includes(symptom)} onChange={() => toggleSymptom(symptom)} /><span className="capitalize">{symptom === 'bodyache' ? 'Body ache' : symptom}</span><span aria-hidden>{symptoms.includes(symptom) ? '✓' : '+'}</span></label>)}</div></fieldset><button className="button-primary mt-7 w-full" disabled={submitting || loadingDoctors || loadingSlots || !doctorId}>{submitting ? 'Confirming appointment...' : `Book ${selectedSlot || 'appointment'}`}</button></section></form></main>
}

function BookingConfirmation({ booking }) {
  return <main className="page-shell page-section"><section className="success-panel"><div className="success-orbit">✓</div><p className="eyebrow">Appointment confirmed</p><h1 className="display-title">You are booked.</h1><p className="mt-3 text-slate-600">{booking.doctor_name} will see you on <strong>{formatDate(booking.appointment_date)}</strong> at <strong>{booking.slot}</strong>.</p><div className="mx-auto mt-8 max-w-md rounded-2xl border border-teal-100 bg-white p-5 text-left shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-brand">Visit reason</p><p className="mt-2 text-slate-700">{booking.reason}</p>{booking.temperature_f && <p className="mt-3 text-sm text-slate-600">Temperature: {booking.temperature_f} °F</p>}</div><div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row"><button type="button" className="button-secondary px-5 py-3" onClick={() => downloadAppointmentInvite(booking)}>Add to calendar</button><Link className="button-primary" to="/dashboard">Go to my dashboard</Link></div></section></main>
}
