export default function ErrorBanner({ message, onDismiss }) {
  if (!message) return null
  return (
    <div role="alert" className="mb-5 flex items-start justify-between gap-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800">
      <span>{message}</span>
      {onDismiss && <button type="button" onClick={onDismiss} aria-label="Dismiss error" className="font-black text-rose-700">×</button>}
    </div>
  )
}

