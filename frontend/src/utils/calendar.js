function toCalendarDate(date, time) {
  const value = new Date(`${date}T${time}:00`)
  const pad = (part) => String(part).padStart(2, '0')
  return `${value.getFullYear()}${pad(value.getMonth() + 1)}${pad(value.getDate())}T${pad(value.getHours())}${pad(value.getMinutes())}00`
}

function escapeCalendarText(value = '') {
  return String(value).replace(/\\/g, '\\\\').replace(/,/g, '\\,').replace(/;/g, '\\;').replace(/\n/g, '\\n')
}

export function downloadAppointmentInvite(appointment) {
  const start = toCalendarDate(appointment.appointment_date, appointment.slot)
  const [hours, minutes] = appointment.slot.split(':').map(Number)
  const endTime = `${String(hours + (minutes === 30 ? 1 : 0)).padStart(2, '0')}:${minutes === 30 ? '00' : '30'}`
  const end = toCalendarDate(appointment.appointment_date, endTime)
  const content = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//CityCare Clinic//Appointment//EN',
    'BEGIN:VEVENT',
    `UID:citycare-${appointment.id}@citycareclinic.com`,
    `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')}`,
    `DTSTART:${start}`,
    `DTEND:${end}`,
    'SUMMARY:CityCare Clinic consultation',
    `DESCRIPTION:${escapeCalendarText(`Dr. Pawan Patil - ${appointment.reason}`)}`,
    'LOCATION:CityCare Clinic\, Nagpur',
    'END:VEVENT',
    'END:VCALENDAR',
  ].join('\r\n')
  const url = URL.createObjectURL(new Blob([content], { type: 'text/calendar;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `citycare-${appointment.appointment_date}-${appointment.slot.replace(':', '')}.ics`
  link.click()
  URL.revokeObjectURL(url)
}

