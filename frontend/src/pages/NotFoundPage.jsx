import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return <main className="page-shell grid min-h-[70vh] place-items-center"><section className="text-center"><p className="eyebrow">404</p><h1 className="display-title">This page does not exist.</h1><Link className="button-primary mt-6" to="/dashboard">Go to dashboard</Link></section></main>
}

