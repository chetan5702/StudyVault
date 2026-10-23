import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { post, request, type NotificationList, type ReminderPreferences } from './api'
import { AsyncForm, Empty, ErrorMessage, Field, LoadingState, Panel } from './components'
import { formatExamDate, localTimezone } from './dates'
import { useData } from './hooks'
import { Icon } from './icons'

type NotificationState = { data: NotificationList | null; error: string; refresh: () => Promise<void> }
const NotificationContext = createContext<NotificationState>({ data: null, error: '', refresh: async () => {} })

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<NotificationList | null>(null)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)
  // Refresh on navigation back to the tab and every 30 seconds while signed in.
  // Actual reminder scheduling and delivery are performed by the server worker.
  useEffect(() => {
    let active = true
    const load = () => request<NotificationList>('/notifications').then(result => {
      if (active) { setData(result); setError('') }
    }).catch(e => { if (active) setError(e.message) })
    void load()
    const timer = setInterval(load, 30_000)
    window.addEventListener('focus', load)
    return () => { active = false; clearInterval(timer); window.removeEventListener('focus', load) }
  }, [version])
  const refresh = useCallback(async () => { setVersion(v => v + 1) }, [])
  return <NotificationContext.Provider value={{ data, error, refresh }}>{children}</NotificationContext.Provider>
}

export function NotificationBell() {
  const { data, error } = useContext(NotificationContext)
  const unread = data?.unread_count ?? 0
  return <Link to="/notifications" className="notification-bell" aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`} title={error ? 'Unable to refresh notifications' : 'Notifications'}>
    <Icon name="bell" size={21} />
    {unread > 0 && <span className="notification-badge" aria-hidden="true">{unread > 99 ? '99+' : unread}</span>}
    {error && <span className="notification-warning" aria-hidden="true">!</span>}
  </Link>
}

export function NotificationsPage() {
  const { data, error, refresh } = useContext(NotificationContext)
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState('')
  async function markRead(id?: string) {
    setBusy(id || 'all'); setActionError('')
    try {
      await post(id ? `/notifications/${id}/read` : '/notifications/read-all', {}, id ? 'PATCH' : 'POST')
      await refresh()
    } catch (e) { setActionError((e as Error).message) }
    finally { setBusy('') }
  }
  return <>
    <div className="page-heading"><div><p className="eyebrow">STUDYVAULT / WORKSPACE</p><h1>Notification center</h1><p className="muted">A little notice. More time to prepare.</p></div><Link className="secondary-button" to="/settings/reminders"><Icon name="settings" size={17} />Reminder settings</Link></div>
    <ErrorMessage message={error || actionError} />
    <Panel><div className="section-toolbar"><div><h2>Exam reminders</h2><p className="muted text-sm" aria-live="polite">{data?.unread_count ?? 0} unread</p></div><div className="button-row"><button className="secondary-button" onClick={() => void refresh()}>Refresh notifications</button><button className="secondary-button" disabled={!!busy || !data?.unread_count} onClick={() => void markRead()}>Mark all as read</button></div></div>
      {!data && !error ? <LoadingState label="Loading notifications…" /> : data?.items.length ? <div className="notifications-list">{data.items.map(notification => <article key={notification.id} className={`notification-item ${notification.read_at ? '' : 'is-unread'}`} data-testid="notification-item">
        <span className="notification-dot" aria-label={notification.read_at ? 'Read notification' : 'Unread notification'} />
        <div className="notification-copy"><h3>{notification.title}</h3><p>{notification.message}</p><small>{formatExamDate(notification.delivered_at || notification.scheduled_for)} · {localTimezone()}</small>{notification.exam_id && <Link className="inline-action" to="/exams">View exam schedule<Icon name="arrow-right" size={17} /></Link>}</div>
        {!notification.read_at && <button className="secondary-button" disabled={!!busy} onClick={() => void markRead(notification.id)}>Mark as read</button>}
      </article>)}</div> : <Empty>You’re all caught up.<br />Your delivered exam reminders will appear here.</Empty>}
    </Panel>
    <p className="page-note">Checks for new notifications every 30 seconds. You can also refresh at any time.</p>
  </>
}

const reminderOptions = [{ minutes: 10080, label: '7 days before' }, { minutes: 4320, label: '3 days before' }, { minutes: 1440, label: '1 day before' }, { minutes: 60, label: '1 hour before' }]

export function ReminderSettingsPage() {
  const preferences = useData<ReminderPreferences>('/notification-preferences')
  return <>
    <div className="page-heading"><div><p className="eyebrow">STUDYVAULT / WORKSPACE</p><h1>Reminder settings</h1><p className="muted">Choose when and where your exam reminders arrive.</p></div><Link className="inline-action" to="/notifications"><Icon name="arrow-left" size={17} />Notification center</Link></div>
    <ErrorMessage message={preferences.error} />
    {preferences.loading ? <LoadingState label="Loading reminder preferences…" /> : preferences.data && <div className="content-grid"><Panel title="Your reminder preferences"><ReminderSettingsForm preferences={preferences.data} /></Panel><div className="reminder-note"><p className="eyebrow">A LITTLE HEAD START</p><h2>Stay a step ahead of exam day.</h2><p>These preferences apply to all your upcoming exams. Changing an exam date automatically updates its pending reminders.</p><p>If all your selected reminder times have already passed for an upcoming exam, one immediate reminder is scheduled. Otherwise, only future reminder times are scheduled.</p><p>Your exam calendar uses your device’s local time: <strong>{localTimezone()}</strong>. Your notification timezone controls dates in reminder messages and emails.</p><Link className="inline-action" to="/exams/calendar">Open exam calendar<Icon name="arrow-right" size={17} /></Link></div></div>}
  </>
}

function ReminderSettingsForm({ preferences }: { preferences: ReminderPreferences }) {
  const [inApp, setInApp] = useState(preferences.in_app_enabled)
  const [email, setEmail] = useState(preferences.email_enabled)
  const [minutes, setMinutes] = useState(preferences.reminder_minutes)
  const [timezone, setTimezone] = useState(preferences.timezone)
  return <AsyncForm label="Save reminder preferences" onSubmit={() => {
    try { new Intl.DateTimeFormat(undefined, { timeZone: timezone }).format() }
    catch { throw new Error('Enter a valid IANA timezone, such as Asia/Kolkata or America/New_York.') }
    if ((inApp || email) && !minutes.length) throw new Error('Choose at least one reminder time, or turn off both delivery channels.')
    return post('/notification-preferences', { in_app_enabled: inApp, email_enabled: email, reminder_minutes: minutes, timezone }, 'PUT')
  }}>
    <fieldset className="settings-fieldset"><legend>Delivery channels</legend><label className="checkbox-row"><input type="checkbox" checked={inApp} onChange={e => setInApp(e.target.checked)} /><span>In-app notifications<small>Show reminders in your private notification center.</small></span></label><label className="checkbox-row"><input type="checkbox" checked={email} disabled={!preferences.email_available && !email} onChange={e => setEmail(e.target.checked)} /><span>Email notifications<small>{preferences.email_available ? 'Send reminders to your account email address.' : 'Email delivery is unavailable until a provider is configured.'}</small></span></label></fieldset>
    <fieldset className="settings-fieldset"><legend>Remind me</legend><div className="reminder-options">{reminderOptions.map(option => <label className="checkbox-row" key={option.minutes}><input type="checkbox" checked={minutes.includes(option.minutes)} onChange={e => setMinutes(current => e.target.checked ? [...current, option.minutes].sort((a, b) => b - a) : current.filter(value => value !== option.minutes))} /><span>{option.label}</span></label>)}</div></fieldset>
    <Field label="Notification timezone"><input value={timezone} onChange={e => setTimezone(e.target.value)} required placeholder="e.g. Asia/Kolkata" /></Field>
    <button type="button" className="secondary-button timezone-button" onClick={() => setTimezone(localTimezone())}>Use my local timezone ({localTimezone()})</button>
  </AsyncForm>
}
