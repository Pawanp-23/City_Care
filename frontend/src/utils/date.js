export function todayISO() {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

export function plusDaysISO(days) {
  const date = new Date(`${todayISO()}T00:00:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

export function formatDate(value, options = { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) {
  return new Intl.DateTimeFormat('en-IN', options).format(new Date(`${value}T00:00:00`))
}

