import { formatDate } from '../utils/date'
import { useTilt } from '../hooks/useTilt'

export default function AppointmentCard({ appointment, onCancel, cancelling }) {
  const tilt = useTilt()
  const cancelled = appointment.status === 'CANCELLED'

  return (
    <article ref={tilt.ref} onMouseMove={tilt.onMouseMove} onMouseLeave={tilt.onMouseLeave} className="tilt-card appointment-card reveal-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-brand">{formatDate(appointment.appointment_date)}</p>
          <h3 className="mt-1 text-2xl font-black text-ink">{appointment.slot}</h3>
        </div>
        <span className={`status-badge ${cancelled ? 'status-cancelled' : 'status-booked'}`}>{cancelled ? 'Cancelled' : appointment.status === 'PENDING' ? 'Awaiting doctor' : appointment.status === 'ACCEPTED' ? 'Accepted' : 'Booked'}</span>
      </div>
      {appointment.doctor_name && <p className="mt-3 text-xs font-bold text-brand">{appointment.doctor_name}</p>}
      <p className="mt-5 line-clamp-2 text-sm leading-6 text-slate-600">{appointment.reason}</p>
      {appointment.temperature_f && <p className="mt-3 inline-flex rounded-lg bg-amber-50 px-2.5 py-1 text-xs font-bold text-amber-700">Temperature: {appointment.temperature_f} °F</p>}
      <div className="mt-5 flex items-end justify-between gap-3 border-t border-slate-100 pt-4">
        <p className="text-xs text-slate-500">{appointment.symptoms?.length ? appointment.symptoms.join(' · ') : 'No symptoms selected'}</p>
        {!cancelled && onCancel && (
          <button type="button" className="text-xs font-bold text-slate-500 underline-offset-4 hover:text-rose-600 hover:underline disabled:opacity-60" onClick={() => onCancel(appointment)} disabled={cancelling}>
            {cancelling ? 'Cancelling…' : 'Cancel'}
          </button>
        )}
      </div>
    </article>
  )
}
