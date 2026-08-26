export default function SlotGrid({ slots, selectedSlot, onSelect, loading, error }) {
  if (loading) return <div className="skeleton h-28 w-full" aria-label="Loading available slots" />
  if (error) return <p className="rounded-xl bg-rose-50 p-4 text-sm font-medium text-rose-700">{error}</p>
  if (!slots.length) return <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-600">No free slots remain for this day. Choose another date.</p>

  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4" role="radiogroup" aria-label="Available appointment times">
      {slots.map((slot) => (
        <button
          key={slot}
          type="button"
          role="radio"
          aria-checked={selectedSlot === slot}
          onClick={() => onSelect(slot)}
          className={`slot-chip ${selectedSlot === slot ? 'slot-chip-selected' : ''}`}
        >
          {slot}
        </button>
      ))}
    </div>
  )
}

