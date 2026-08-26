export default function FormInput({ label, id, error, className = '', ...inputProps }) {
  return (
    <label className={`block ${className}`} htmlFor={id}>
      <span className="mb-2 block text-sm font-semibold text-slate-700">{label}</span>
      <input
        id={id}
        className={`field-input ${error ? 'border-rose-400 ring-rose-100' : ''}`}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        {...inputProps}
      />
      {error && <span id={`${id}-error`} className="mt-1.5 block text-xs font-medium text-rose-600">{error}</span>}
    </label>
  )
}

