import { useEffect, useState, type ReactNode, type FormEvent } from 'react'
import { Icon } from './icons'

export function Panel({ children, title }: { children: ReactNode; title?: string }) {
  return <section className="panel">{title && <h2>{title}</h2>}{children}</section>
}
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}</label>
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>
}
export function ErrorMessage({ message }: { message: string }) {
  return message ? <p role="alert" className="error">{message}</p> : null
}
export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return <div className="loading-state" role="status" aria-live="polite"><span className="spinner" aria-hidden="true" /><span>{label}</span></div>
}
export function AsyncForm({ children, onSubmit, label = 'Save', onSuccess, resetOnSuccess = false, successMessage = 'Saved successfully.' }: { children: ReactNode; onSubmit: (data: FormData) => Promise<unknown>; label?: string; onSuccess?: () => void; resetOnSuccess?: boolean; successMessage?: string | false }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    setBusy(true); setError(''); setSuccess('')
    try { await onSubmit(new FormData(form)); if (resetOnSuccess) form.reset(); setSuccess(successMessage || ''); onSuccess?.() }
    catch (e) { setError(e instanceof Error ? e.message : 'Something went wrong') }
    finally { setBusy(false) }
  }
  return <form onSubmit={submit} className="form-grid" aria-busy={busy}>{children}<ErrorMessage message={error} />{success && <p role="status" className="success"><Icon name="check" size={17} />{success}</p>}<button disabled={busy} className="button" type="submit">{busy && <span className="spinner spinner-light" aria-hidden="true" />}{busy ? 'Please wait…' : label}</button></form>
}
export function Countdown({ date }: { date: string }) {
  const [now, setNow] = useState(Date.now)
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(timer) }, [])
  const minutes = Math.max(0, Math.floor((new Date(date).getTime() - now) / 60_000))
  return <span className="countdown"><Icon name="clock" size={16} />{new Date(date).getTime() <= now ? 'Completed' : minutes === 0 ? 'Less than a minute remaining' : `${Math.floor(minutes / 1440)}d ${Math.floor(minutes % 1440 / 60)}h ${minutes % 60}m remaining`}</span>
}
