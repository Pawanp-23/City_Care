import { formatDate } from '../utils/date'

export default function ScheduleTable({ schedule, date, isFiltered, onAccept, onPrescribe }) {
  if (!schedule?.length) {
    return <div className="empty-state"><span className="text-3xl">○</span><p>{isFiltered ? 'No appointments match those filters.' : `No appointments on ${formatDate(date)}.`}</p><span>{isFiltered ? 'Clear or change the filters to see the full schedule.' : 'The schedule is clear for this date.'}</span></div>
  }
  return (
    <div className="schedule-table-wrap">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
            <tr><th>Time</th><th>Patient</th><th>Status</th><th>Reason</th><th>Temp.</th><th>Symptoms</th><th>Care action</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {schedule.map((appointment, index) => (
              <tr key={appointment.id} className="schedule-row" style={{ animationDelay: `${index * 45}ms` }}>
                <td className="whitespace-nowrap font-bold text-ink">{appointment.slot}</td>
                <td className="whitespace-nowrap font-semibold text-slate-700">{appointment.patient_name}</td>
                <td className="whitespace-nowrap">
                  <span className={`status-badge ${appointment.status === 'ACCEPTED' ? 'status-booked' : 'status-pending'}`}>
                    {appointment.status === 'ACCEPTED' ? 'Accepted' : 'Pending'}
                  </span>
                </td>
                <td className="min-w-48 text-slate-600">{appointment.reason}</td>
                <td className="whitespace-nowrap text-slate-600">{appointment.temperature_f ? `${appointment.temperature_f} F` : '-'}</td>
                <td className="min-w-44 text-slate-600">{appointment.symptoms?.length ? appointment.symptoms.join(', ') : '-'}</td>
                <td className="whitespace-nowrap">
                  {appointment.status === 'ACCEPTED' ? (
                    <button className="table-action" onClick={() => onPrescribe?.(appointment)}>Create prescription</button>
                  ) : (
                    <button className="table-action" onClick={() => onAccept?.(appointment)}>Accept visit</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
