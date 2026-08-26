import { useTilt } from '../hooks/useTilt'

export default function StatCard({ label, value, detail, accent = 'teal' }) {
  const tilt = useTilt()
  return (
    <article ref={tilt.ref} onMouseMove={tilt.onMouseMove} onMouseLeave={tilt.onMouseLeave} className={`tilt-card stat-card stat-${accent}`}>
      <p className="text-sm font-bold text-slate-600">{label}</p>
      <p className="mt-4 text-4xl font-black tracking-tight text-ink">{value ?? '—'}</p>
      <p className="mt-2 text-xs font-medium text-slate-500">{detail}</p>
    </article>
  )
}

