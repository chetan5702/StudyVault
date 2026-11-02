import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { BrowserRouter, NavLink, Navigate, Outlet, Route, Routes, Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { request, post, session, download, type User, type AuthResult, type Subject, type Unit, type Material, type Profile, type Dashboard, type Exam } from './api'
import { Panel, Field, Empty, ErrorMessage, AsyncForm, Countdown, LoadingState } from './components'
import { useData } from './hooks'
import { ExamsPage } from './Exams'
import { NotificationBell, NotificationProvider, NotificationsPage, ReminderSettingsPage } from './Notifications'
import { formatExamDate, localTimezone } from './dates'
import { FileTypeIcon, Icon, type IconName } from './icons'

const Auth = createContext<{ user: User | null; login: (result: AuthResult) => void; logout: () => void }>({ user: null, login: () => {}, logout: () => {} })
function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    const lookup = session.token() ? request<User>('/auth/me') : Promise.resolve(null)
    lookup.then(u => { if (active) setUser(u) }).catch(e => { if (active && session.token()) setError(e.message) }).finally(() => { if (active) setReady(true) })
    return () => { active = false }
  }, [attempt])
  useEffect(() => {
    const clear = () => { setUser(null); session.clear() }
    window.addEventListener('studyvault:unauthorized', clear)
    return () => window.removeEventListener('studyvault:unauthorized', clear)
  }, [])
  if (!ready) return <div className="loading">Opening StudyVault…</div>
  if (error) return <main className="auth-card"><ErrorMessage message={error} /><button className="button" onClick={() => { setError(''); setReady(false); setAttempt(n => n + 1) }}>Retry connection</button></main>
  return <Auth.Provider value={{ user, login: result => { if (!result.access_token) throw new Error('A verified account is required to start a session.'); session.set(result.access_token); setUser(result.user) }, logout: () => { session.clear(); setUser(null) } }}>{children}</Auth.Provider>
}

function AuthPage({ register = false }: { register?: boolean }) {
  const auth = useContext(Auth)
  const navigate = useNavigate()
  if (auth.user) return <Navigate to={register ? '/profile' : '/'} replace />
  return <main className="auth-layout"><div className="auth-story"><Link to="/" className="brand"><Icon name="vault" size={25} />StudyVault</Link><p className="eyebrow">YOUR ACADEMIC HOME</p><h1>A little more organized.<br />A lot more prepared.</h1><p>Keep your subjects, study materials and upcoming exams together in one private workspace.</p><div className="story-note">Built for the next chapter of your studies.</div></div><div className="auth-card"><p className="eyebrow">LET’S GET STARTED</p><h2>{register ? 'Create your account' : 'Welcome back'}</h2><p className="muted">{register ? 'Make room for a more focused semester.' : 'Your study space is ready when you are.'}</p><AsyncForm label={register ? 'Create account' : 'Log in'} onSubmit={async data => {
    const registration = register ? { full_name: data.get('name'), phone_number: String(data.get('phone_number') || '').trim() || null } : {}
    const email = String(data.get('email') || '').trim()
    if (register) {
      const emailDomain = email.split('@').pop()?.toLowerCase() || ''
      if (emailDomain !== 'suh.edu.in' && !emailDomain.endsWith('.suh.edu.in')) {
        throw new Error('Use your official SUH university email (such as student@aiml.suh.edu.in, student@cse.suh.edu.in or student@ds.suh.edu.in).')
      }
    }
    const result = await post<AuthResult>(`/auth/${register ? 'register' : 'login'}`, { email, password: data.get('password'), ...registration })
    if (result.verification_required || !result.access_token) {
      navigate(`/check-email?email=${encodeURIComponent(email)}`, { replace: true })
      return
    }
    auth.login(result); navigate(register ? '/profile' : '/')
  }}>{register && <><Field label="Full name"><input name="name" autoComplete="name" required maxLength={120} /></Field><PhoneField helpId="registration-phone-help" /></>}<Field label="Email address"><input name="email" type="email" autoComplete="email" placeholder={register ? "student@aiml.suh.edu.in" : undefined} required /></Field>{register && <p className="muted text-sm">New accounts require an official SUH email: @suh.edu.in or a department address such as @aiml.suh.edu.in, @cse.suh.edu.in or @ds.suh.edu.in. Verify the email link to activate your account. Existing accounts can still log in.</p>}<Field label="Password"><input name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} required minLength={register ? 8 : undefined} maxLength={72} /></Field>{register && <p className="muted text-sm">Use at least 8 characters, up to 72 UTF-8 bytes.</p>}</AsyncForm>{!register && <p className="auth-secondary-link"><Link to="/forgot-password">Forgot your password?</Link></p>}<p className="auth-switch">{register ? 'Already have an account?' : 'New to StudyVault?'} <Link to={register ? '/login' : '/register'}>{register ? 'Log in' : 'Create an account'}</Link></p></div></main>
}

function PhoneField({ defaultValue = '', helpId }: { defaultValue?: string; helpId: string }) {
  return <Field label="Phone number (optional)"><input name="phone_number" type="tel" autoComplete="tel" inputMode="tel" defaultValue={defaultValue} pattern={'\\+?[0-9 \\(\\)\\-]{7,24}'} maxLength={25} aria-describedby={helpId} title="Enter 7–15 digits. Spaces, parentheses and hyphens are okay." /><small id={helpId}>7–15 digits; spaces, parentheses and hyphens are okay.</small></Field>
}

function PublicAccountPage({ title, subtitle, children }: { title: string; subtitle: ReactNode; children: ReactNode }) {
  return <main className="auth-layout"><div className="auth-story"><Link to="/" className="brand"><Icon name="vault" size={25} />StudyVault</Link><p className="eyebrow">YOUR ACADEMIC HOME</p><h1>A little more organized.<br />A lot more prepared.</h1><p>Keep your subjects, study materials and upcoming exams together in one private workspace.</p><div className="story-note">Built for the next chapter of your studies.</div></div><div className="auth-card"><p className="eyebrow">ACCOUNT SECURITY</p><h2>{title}</h2><p className="muted">{subtitle}</p>{children}</div></main>
}

type MessageResponse = { message: string }

function CheckEmailPage() {
  const auth = useContext(Auth)
  const [searchParams] = useSearchParams()
  const email = searchParams.get('email') || ''
  const [message, setMessage] = useState('')
  if (auth.user) return <Navigate to="/" replace />
  return <PublicAccountPage title="Check your email" subtitle={email ? <>We sent a verification link to <strong>{email}</strong>. Open it to activate your account.</> : 'Open the verification link sent to your email address.'}>
    {message && <p className="success auth-notice" role="status">{message}</p>}
    <AsyncForm label="Send another verification email" successMessage={false} onSubmit={async data => {
      const result = await post<MessageResponse>('/auth/resend-verification', { email: data.get('email') })
      setMessage(result.message)
    }}><Field label="Email address"><input name="email" type="email" autoComplete="email" defaultValue={email} required /></Field></AsyncForm>
    <p className="auth-switch"><Link to="/login">Back to login</Link></p>
  </PublicAccountPage>
}

function VerifyEmailPage() {
  const auth = useContext(Auth)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [error, setError] = useState('')
  const started = useRef(false)
  useEffect(() => {
    if (!token) return
    if (started.current) return
    started.current = true
    post<AuthResult>('/auth/verify-email', { token }).then(result => {
      if (!result.access_token || result.verification_required) {
        setError('Your email could not be verified. Request a new verification link.')
        return
      }
      auth.login(result)
      navigate('/profile', { replace: true })
    }).catch(cause => setError((cause as Error).message))
  }, [auth, navigate, token])
  const displayedError = token ? error : 'This verification link is missing its token.'
  return <PublicAccountPage title="Verifying your email" subtitle="Please wait while we activate your StudyVault account.">
    {displayedError ? <><ErrorMessage message={displayedError} /><p className="auth-switch"><Link to="/check-email">Request another verification email</Link></p></> : <p className="auth-notice" role="status">Verifying your email address...</p>}
  </PublicAccountPage>
}

function ForgotPasswordPage() {
  const auth = useContext(Auth)
  const [message, setMessage] = useState('')
  if (auth.user) return <Navigate to="/" replace />
  return <PublicAccountPage title="Reset your password" subtitle="Enter your account email and we will send you a secure reset link.">
    {message && <p className="success auth-notice" role="status">{message}</p>}
    <AsyncForm label="Send reset link" successMessage={false} onSubmit={async data => {
      const result = await post<MessageResponse>('/auth/request-password-reset', { email: data.get('email') })
      setMessage(result.message)
    }}><Field label="Email address"><input name="email" type="email" autoComplete="email" required /></Field></AsyncForm>
    <p className="auth-switch"><Link to="/login">Back to login</Link></p>
  </PublicAccountPage>
}

function ResetPasswordPage() {
  const auth = useContext(Auth)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [message, setMessage] = useState('')
  if (auth.user) return <Navigate to="/" replace />
  if (message) return <PublicAccountPage title="Password updated" subtitle={message}><p className="auth-switch"><Link to="/login">Log in with your new password</Link></p></PublicAccountPage>
  return <PublicAccountPage title="Choose a new password" subtitle="Use at least 8 characters, up to 72 UTF-8 bytes.">
    {!token ? <><ErrorMessage message="This password reset link is missing its token." /><p className="auth-switch"><Link to="/forgot-password">Request a new reset link</Link></p></> : <AsyncForm label="Update password" successMessage={false} onSubmit={async data => {
      const password = String(data.get('password') || '')
      if (password !== String(data.get('password_confirmation') || '')) throw new Error('Passwords do not match.')
      const result = await post<MessageResponse>('/auth/confirm-password-reset', { token, new_password: password })
      setMessage(result.message)
      navigate('/reset-password', { replace: true })
    }}><Field label="New password"><input name="password" type="password" autoComplete="new-password" required minLength={8} maxLength={72} /></Field><Field label="Confirm new password"><input name="password_confirmation" type="password" autoComplete="new-password" required minLength={8} maxLength={72} /></Field></AsyncForm>}
    <p className="auth-switch"><Link to="/login">Back to login</Link></p>
  </PublicAccountPage>
}

const navigation: { path: string; icon: IconName; label: string }[] = [
  { path: '/', icon: 'dashboard', label: 'Dashboard' },
  { path: '/subjects', icon: 'book', label: 'Subjects' },
  { path: '/materials', icon: 'files', label: 'Materials' },
  { path: '/exams', icon: 'calendar', label: 'Exams' },
  { path: '/settings/reminders', icon: 'bell', label: 'Reminders' },
  { path: '/profile', icon: 'user', label: 'Academic profile' },
]

function Layout() {
  const { user, logout } = useContext(Auth)
  const [open, setOpen] = useState(false)
  if (!user) return <Navigate to="/login" replace />
  return <NotificationProvider key={user.id}><div className="app-shell">
    <aside id="workspace-navigation" className={`sidebar ${open ? 'is-open' : ''}`}>
      <Link className="brand" to="/"><Icon name="vault" size={25} />StudyVault</Link>
      <p className="nav-label">WORKSPACE</p>
      <nav>{navigation.map(item => <NavLink end={item.path === '/'} key={item.path} to={item.path} onClick={() => setOpen(false)}><Icon name={item.icon} size={20} />{item.label}</NavLink>)}</nav>
      <div className="sidebar-bottom"><div className="avatar">{user.full_name.charAt(0).toUpperCase()}</div><div className="account-copy"><strong>{user.full_name}</strong><small>Student workspace</small></div><button onClick={logout} className="logout">Log out</button></div>
    </aside>
    {open && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <div className="workspace"><header className="topbar"><button className="menu-button" onClick={() => setOpen(!open)} aria-label="Toggle navigation" aria-controls="workspace-navigation" aria-expanded={open}><Icon name="menu" size={23} /></button><strong>My study space</strong><div className="header-actions"><span className="private-badge"><Icon name="lock" size={14} />Private & personal</span><NotificationBell /></div></header><main className="page"><Outlet /></main></div>
  </div></NotificationProvider>
}
function Heading({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">STUDYVAULT / WORKSPACE</p><h1>{title}</h1><p className="muted">{subtitle}</p></div>{action}</div>
}
function DashboardPage() {
  const { data, loading, error, reload: reloadDashboard } = useData<Dashboard>('/dashboard')
  const profile = useData<Profile>('/profile/me')
  const { data: upcomingData, loading: upcomingLoading, error: upcomingError, reload: reloadUpcoming } = useData<Exam[]>('/exams?status=upcoming')
  const subjects = useData<Subject[]>('/subjects')
  const refreshedExam = useRef<string | null>(null)
  const nextExamTime = data?.next_exam?.scheduled_for
  useEffect(() => {
    if (!nextExamTime || refreshedExam.current === nextExamTime) return
    let timer: number
    const refreshWhenDue = () => {
      const remaining = Date.parse(nextExamTime) - Date.now()
      if (remaining > 0) {
        // Browser timers overflow beyond roughly 25 days; recheck distant exams.
        timer = window.setTimeout(refreshWhenDue, Math.min(remaining + 100, 2_147_483_647))
      } else {
        refreshedExam.current = nextExamTime
        reloadDashboard()
        reloadUpcoming()
      }
    }
    refreshWhenDue()
    return () => clearTimeout(timer)
  }, [nextExamTime, reloadDashboard, reloadUpcoming])
  useEffect(() => {
    const refreshVisiblePage = () => {
      if (document.visibilityState === 'visible') {
        reloadDashboard()
        reloadUpcoming()
      }
    }
    window.addEventListener('focus', refreshVisiblePage)
    document.addEventListener('visibilitychange', refreshVisiblePage)
    return () => {
      window.removeEventListener('focus', refreshVisiblePage)
      document.removeEventListener('visibilitychange', refreshVisiblePage)
    }
  }, [reloadDashboard, reloadUpcoming])
  const subjectNames = new Map((subjects.data || []).map(subject => [subject.id, subject.name]))
  const deadlines = (upcomingData || []).slice(0, 4)
  const loadError = error || profile.error || upcomingError || subjects.error
  return <>
    <Heading title="Dashboard" subtitle="See what needs attention next and move quickly into your study work." action={<Link className="button" to="/materials"><Icon name="upload" size={18} />Upload material</Link>} />
    <ErrorMessage message={loadError} />
    {loading ? <LoadingState label="Loading your dashboard…" /> : data && <>
      {!profile.loading && !profile.data?.academic_year && <div className="onboarding"><div><strong>Complete your academic profile</strong><p>Add your academic year and semester so StudyVault can organize your workspace.</p></div><Link className="inline-action" to="/profile">Complete profile<Icon name="arrow-right" size={17} /></Link></div>}
      <section className="quick-actions" aria-labelledby="quick-actions-title"><div className="section-heading"><div><p className="eyebrow">QUICK ACTIONS</p><h2 id="quick-actions-title">Keep your semester moving</h2></div></div><div className="quick-action-grid">
        <Link to="/subjects" className="quick-action"><span><Icon name="plus" size={20} /></span><div><strong>Add a subject</strong><small>Organize a new course</small></div><Icon name="arrow-right" size={18} /></Link>
        <Link to="/materials" className="quick-action"><span><Icon name="upload" size={20} /></span><div><strong>Upload material</strong><small>Save notes and documents</small></div><Icon name="arrow-right" size={18} /></Link>
        <Link to="/exams" className="quick-action"><span><Icon name="calendar" size={20} /></span><div><strong>Schedule an exam</strong><small>Add your next deadline</small></div><Icon name="arrow-right" size={18} /></Link>
      </div></section>
      <div className="dashboard-priority-grid">
        <Panel title="Upcoming deadlines">{upcomingLoading ? <LoadingState label="Loading upcoming exams…" /> : deadlines.length ? <div className="deadline-list">{deadlines.map((exam, index) => <article className={`deadline-row ${index === 0 ? 'is-next' : ''}`} key={exam.id}><div className="deadline-date" aria-hidden="true"><span>{new Date(exam.scheduled_for).toLocaleDateString(undefined, { month: 'short' })}</span><strong>{new Date(exam.scheduled_for).toLocaleDateString(undefined, { day: '2-digit' })}</strong></div><div className="deadline-copy"><div className="deadline-heading"><div><p>{subjectNames.get(exam.subject_id) || 'Exam'}</p><h3>{exam.title}</h3></div>{index === 0 && <span className="priority-badge">Next</span>}</div><Countdown date={exam.scheduled_for} /><small>{formatExamDate(exam.scheduled_for)} · {localTimezone()}</small></div></article>)}</div> : <Empty>No upcoming exams.<br /><Link className="inline-action" to="/exams">Schedule an exam<Icon name="arrow-right" size={17} /></Link></Empty>}<Link className="inline-action panel-action" to="/exams">View full exam schedule<Icon name="arrow-right" size={17} /></Link></Panel>
        <Panel title="Recent materials">{data.recent_materials.length ? <div className="recent-materials">{data.recent_materials.slice(0, 4).map(material => <Link to="/materials" key={material.id} className="recent-material-row"><FileTypeIcon fileName={material.file_name} mimeType={material.mime_type} /><div><strong>{material.title}</strong><small title={material.file_name}>{material.file_name}</small></div><Icon name="arrow-right" size={18} /></Link>)}</div> : <Empty>Your library is empty.<br /><Link className="inline-action" to="/materials">Upload your first material<Icon name="arrow-right" size={17} /></Link></Empty>}<Link className="inline-action panel-action" to="/materials">Open materials library<Icon name="arrow-right" size={17} /></Link></Panel>
      </div>
      <section className="overview-strip" aria-label="Workspace overview"><div><Icon name="book" size={20} /><span><strong>{data.stats.subjects}</strong> Subjects</span></div><div><Icon name="files" size={20} /><span><strong>{data.stats.materials}</strong> Materials</span></div><div><Icon name="calendar" size={20} /><span><strong>{data.stats.upcoming_exams}</strong> Upcoming exams</span></div></section>
    </>}
  </>
}
function SubjectsPage() {
  const { data, loading, error, reload } = useData<Subject[]>('/subjects')
  const [editing, setEditing] = useState<Subject | null>(null)
  const [deleting, setDeleting] = useState<Subject | null>(null)
  const [message, setMessage] = useState('')
  const [formVersion, setFormVersion] = useState(0)
  function saved() {
    setMessage(editing ? 'Subject updated.' : 'Subject created.')
    if (editing) {
      setEditing(null)
      setFormVersion(value => value + 1)
    }
    reload()
  }
  return <>
    <Heading title="Your subjects" subtitle="Give each course a home for units, notes and exam preparation." />
    {message && <p role="status" className="success action-notice">{message}</p>}
    <div className="content-grid"><Panel title="Semester subjects"><ErrorMessage message={error} />{loading ? <LoadingState label="Loading subjects…" /> : data?.length ? data.map(subject => <article className="subject-row" key={subject.id}>
      <Link className="subject-link" to={`/subjects/${subject.id}`}><span className="subject-icon"><Icon name="book" size={21} /></span><div><small>{subject.code}</small><h3>{subject.name}</h3><p className="muted">{subject.semester ? `Semester ${subject.semester}` : 'Open subject to manage units'}</p></div></Link>
      <div className="button-row subject-actions"><button className="secondary-button" aria-label={`Edit ${subject.name}`} onClick={() => { setEditing(subject); setMessage('') }}><Icon name="edit" size={16} />Edit</button><button className="text-button danger-text" aria-label={`Delete ${subject.name}`} onClick={() => setDeleting(subject)}><Icon name="trash" size={16} />Delete</button><Link className="icon-link" aria-label={`Open ${subject.name}`} to={`/subjects/${subject.id}`}><Icon name="arrow-right" size={19} /></Link></div>
    </article>) : <Empty>No subjects yet. Create your first subject to start organizing your semester.</Empty>}</Panel>
    <Panel title={editing ? 'Edit subject' : 'Create a subject'}><SubjectForm key={`${editing?.id || 'new'}-${formVersion}`} subject={editing} saved={saved} cancel={() => setEditing(null)} /></Panel></div>
    {deleting && <DeleteSubjectDialog subject={deleting} close={() => setDeleting(null)} deleted={() => { if (editing?.id === deleting.id) setEditing(null); setDeleting(null); setMessage('Subject deleted.'); reload() }} />}
  </>
}
function SubjectForm({ subject, saved, cancel }: { subject: Subject | null; saved: () => void; cancel: () => void }) {
  return <AsyncForm label={subject ? 'Save subject changes' : 'Create subject'} resetOnSuccess={!subject} onSuccess={saved} onSubmit={data => post(subject ? `/subjects/${subject.id}` : '/subjects', { code: data.get('code'), name: data.get('name'), semester: Number(data.get('semester')) || null }, subject ? 'PATCH' : 'POST')}>
    <Field label="Subject code"><input name="code" defaultValue={subject?.code || ''} placeholder="e.g. CS101" required /></Field>
    <Field label="Subject name"><input name="name" defaultValue={subject?.name || ''} placeholder="e.g. Computer Science" required /></Field>
    <Field label="Semester (optional)"><input name="semester" type="number" min={1} max={20} defaultValue={subject?.semester || ''} /></Field>
    {subject && <button type="button" className="secondary-button" onClick={cancel}>Cancel editing</button>}
  </AsyncForm>
}
function DeleteSubjectDialog({ subject, close, deleted }: { subject: Subject; close: () => void; deleted: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { dialog.current?.showModal() }, [])
  async function remove() {
    setBusy(true); setError('')
    try { await request(`/subjects/${subject.id}`, { method: 'DELETE' }); deleted() }
    catch (e) { setError((e as Error).message); setBusy(false) }
  }
  return <dialog ref={dialog} className="confirm-dialog" aria-labelledby="delete-subject-title" onCancel={event => { event.preventDefault(); if (!busy) close() }}><h2 id="delete-subject-title">Delete subject?</h2><p>Delete <strong>{subject.code} · {subject.name}</strong>? This action cannot be undone.</p><ErrorMessage message={error} /><div className="button-row"><button className="secondary-button" autoFocus disabled={busy} onClick={close}>Keep subject</button><button className="button danger-button" disabled={busy} onClick={() => void remove()}>{busy ? 'Deleting…' : 'Delete subject'}</button></div></dialog>
}
function SubjectPage() {
  const { id = '' } = useParams()
  const subject = useData<Subject>(`/subjects/${id}`)
  const units = useData<Unit[]>(`/subjects/${id}/units`)
  const [editing, setEditing] = useState<Unit | null>(null)
  const [deleting, setDeleting] = useState<Unit | null>(null)
  const [message, setMessage] = useState('')
  function saved() {
    setMessage(editing ? 'Unit updated.' : 'Unit added.')
    setEditing(null)
    units.reload()
  }
  return <>
    <Heading title={subject.data?.name || 'Subject'} subtitle={subject.data?.code || 'Manage your subject units.'} action={<Link className="inline-action" to="/subjects"><Icon name="arrow-left" size={17} />All subjects</Link>} />
    <ErrorMessage message={subject.error || units.error} />
    {message && <p role="status" className="success action-notice">{message}</p>}
    <div className="content-grid"><Panel title="Units">{units.loading ? <LoadingState label="Loading units…" /> : units.data?.length ? units.data.map(unit => <div className="list-row unit-row" key={unit.id}><div className="unit-details"><span className="unit-number">{unit.order_index}</span><strong>{unit.name}</strong></div><div className="button-row"><button className="secondary-button" aria-label={`Edit ${unit.name}`} onClick={() => { setEditing(unit); setMessage('') }}><Icon name="edit" size={16} />Edit</button><button className="text-button danger-text" aria-label={`Delete ${unit.name}`} onClick={() => setDeleting(unit)}><Icon name="trash" size={16} />Delete</button></div></div>) : <Empty>Add a unit to organize your subject’s study materials.</Empty>}<Link to={`/materials?subject_id=${encodeURIComponent(id)}`} className="inline-action panel-action">View this subject’s materials<Icon name="arrow-right" size={17} /></Link></Panel><Panel title={editing ? 'Edit unit' : 'Add a unit'}><UnitForm key={editing?.id || 'new'} subjectId={id} unit={editing} saved={saved} cancel={() => setEditing(null)} /></Panel></div>
    {deleting && <DeleteUnitDialog subjectId={id} unit={deleting} close={() => setDeleting(null)} deleted={() => { if (editing?.id === deleting.id) setEditing(null); setDeleting(null); setMessage('Unit deleted.'); units.reload() }} />}
  </>
}
function UnitForm({ subjectId, unit, saved, cancel }: { subjectId: string; unit: Unit | null; saved: () => void; cancel: () => void }) {
  return <AsyncForm label={unit ? 'Save unit changes' : 'Add unit'} resetOnSuccess={!unit} onSuccess={saved} onSubmit={data => post(`/subjects/${subjectId}/units${unit ? `/${unit.id}` : ''}`, { subject_id: subjectId, name: data.get('name'), order_index: Number(data.get('order')) }, unit ? 'PATCH' : 'POST')}>
    <Field label="Unit name"><input name="name" defaultValue={unit?.name || ''} required /></Field>
    <Field label="Unit number"><input name="order" type="number" defaultValue={unit?.order_index || 1} min={1} required /></Field>
    {unit && <button type="button" className="secondary-button" onClick={cancel}>Cancel editing</button>}
  </AsyncForm>
}
function DeleteUnitDialog({ subjectId, unit, close, deleted }: { subjectId: string; unit: Unit; close: () => void; deleted: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { dialog.current?.showModal() }, [])
  async function remove() {
    setBusy(true); setError('')
    try { await request(`/subjects/${subjectId}/units/${unit.id}`, { method: 'DELETE' }); deleted() }
    catch (e) { setError((e as Error).message); setBusy(false) }
  }
  return <dialog ref={dialog} className="confirm-dialog" aria-labelledby="delete-unit-title" onCancel={event => { event.preventDefault(); if (!busy) close() }}><h2 id="delete-unit-title">Delete unit?</h2><p>Delete <strong>{unit.name}</strong>? Materials assigned to this unit must be removed or reassigned first.</p><ErrorMessage message={error} /><div className="button-row"><button className="secondary-button" autoFocus disabled={busy} onClick={close}>Keep unit</button><button className="button danger-button" disabled={busy} onClick={() => void remove()}>{busy ? 'Deleting…' : 'Delete unit'}</button></div></dialog>
}
function SubjectSelect({ subjects, value, onChange }: { subjects: Subject[]; value: string; onChange: (v: string) => void }) {
  return <Field label="Subject"><select name="subject_id" value={value} onChange={e => onChange(e.target.value)} required><option value="">Select a subject</option>{subjects.map(s => <option key={s.id} value={s.id}>{s.code} · {s.name}</option>)}</select></Field>
}
function MaterialFilters({ subjects, search, category, subjectId, apply }: { subjects: Subject[]; search: string; category: string; subjectId: string; apply: (search: string, category: string, subjectId: string) => void }) {
  const [draftSearch, setDraftSearch] = useState(search)
  const [draftCategory, setDraftCategory] = useState(category)
  const [draftSubject, setDraftSubject] = useState(subjectId)
  const filtered = !!(search || category || subjectId)
  return <form className="material-filters" onSubmit={event => { event.preventDefault(); apply(draftSearch, draftCategory, draftSubject) }}><Field label="Search materials"><input type="search" value={draftSearch} onChange={event => setDraftSearch(event.target.value)} placeholder="Title or file name" /></Field><Field label="Category"><select value={draftCategory} onChange={event => setDraftCategory(event.target.value)}><option value="">All categories</option><option value="notes">Notes</option><option value="assignment">Assignment</option><option value="reference">Reference</option><option value="past-paper">Past paper</option></select></Field><Field label="Filter by subject"><select value={draftSubject} onChange={event => setDraftSubject(event.target.value)}><option value="">All subjects</option>{subjects.map(subject => <option key={subject.id} value={subject.id}>{subject.code} · {subject.name}</option>)}</select></Field><div className="button-row material-filter-actions"><button className="button" type="submit">Apply filters</button>{filtered && <button className="secondary-button" type="button" onClick={() => apply('', '', '')}>Clear filters</button>}</div></form>
}
function MaterialsPage() {
  const { user } = useContext(Auth)
  const [searchParams, setSearchParams] = useSearchParams()
  const search = searchParams.get('search')?.trim() || ''
  const category = searchParams.get('category')?.trim() || ''
  const subjectFilter = searchParams.get('subject_id')?.trim() || ''
  const query = new URLSearchParams()
  if (search) query.set('search', search)
  if (category) query.set('category', category)
  if (subjectFilter) query.set('subject_id', subjectFilter)
  const materials = useData<Material[]>(`/materials${query.size ? `?${query}` : ''}`)
  const subjects = useData<Subject[]>('/subjects')
  const uploadConfig = useData<{ max_upload_size_bytes: number }>('/materials/config')
  const uploadLimit = uploadConfig.data?.max_upload_size_bytes
  const uploadLimitText = uploadLimit === undefined ? '' : `${(uploadLimit / (1024 * 1024)).toLocaleString(undefined, { maximumFractionDigits: 3 })} MiB (${uploadLimit.toLocaleString()} bytes)`
  const [sid, setSid] = useState(subjectFilter)
  const [unitResult, setUnitResult] = useState<{ subjectId: string; data: Unit[]; error: string } | null>(null)
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState('')
  const [deleting, setDeleting] = useState<Material | null>(null)
  const [message, setMessage] = useState('')
  useEffect(() => {
    let active = true
    if (!sid) return () => { active = false }
    request<Unit[]>(`/subjects/${sid}/units`).then(data => { if (active) setUnitResult({ subjectId: sid, data, error: '' }) }).catch(e => { if (active) setUnitResult({ subjectId: sid, data: [], error: e.message }) })
    return () => { active = false }
  }, [sid])
  function applyFilters(nextSearch: string, nextCategory: string, nextSubject: string) {
    const next = new URLSearchParams()
    if (nextSearch.trim()) next.set('search', nextSearch.trim())
    if (nextCategory) next.set('category', nextCategory)
    if (nextSubject) next.set('subject_id', nextSubject)
    setSearchParams(next)
  }
  const filtered = !!(search || category || subjectFilter)
  const units = unitResult?.subjectId === sid ? unitResult.data : []
  const unitError = unitResult?.subjectId === sid ? unitResult.error : ''
  return <><Heading title="Materials library" subtitle="Your notes and documents, securely stored and ready to revisit." />{message && <p role="status" className="success action-notice">{message}</p>}<ErrorMessage message={materials.error || subjects.error || error} /><div className="content-grid"><Panel title="Your study materials"><MaterialFilters key={`${search}\u0000${category}\u0000${subjectFilter}`} subjects={subjects.data || []} search={search} category={category} subjectId={subjectFilter} apply={applyFilters} />{materials.loading ? <LoadingState label="Loading materials…" /> : materials.data?.length ? materials.data.map(material => <article className="material-row" key={material.id}><FileTypeIcon fileName={material.file_name} mimeType={material.mime_type} /><div className="material-copy"><h3>{material.title}</h3><small className="material-file-name" title={material.file_name}>{material.file_name}</small><small>{(material.size_bytes / 1024).toFixed(1)} KB</small><span className="tag">{material.category}</span><span className="tag">{material.visibility}</span></div><div className="button-row material-actions"><button disabled={!!downloading} className="secondary-button" onClick={async () => { setError(''); setDownloading(material.id); try { await download(material) } catch (e) { setError((e as Error).message) } finally { setDownloading('') } }}>{downloading === material.id ? <><span className="spinner" aria-hidden="true" />Downloading…</> : <><Icon name="download" size={16} />Download</>}</button>{material.user_id === user?.id && <button className="text-button danger-text" aria-label={`Delete ${material.title}`} onClick={() => setDeleting(material)}><Icon name="trash" size={16} />Delete</button>}</div></article>) : <Empty>{filtered ? 'No materials match these filters.' : 'No materials yet. Upload your first PDF after creating a subject.'}</Empty>}</Panel><Panel title="Upload a material"><ErrorMessage message={uploadConfig.error} />{subjects.data?.length ? uploadConfig.loading ? <LoadingState label="Loading upload settings…" /> : uploadLimit === undefined ? <button className="secondary-button" onClick={uploadConfig.reload}>Retry upload settings</button> : <AsyncForm label="Upload material" onSuccess={materials.reload} onSubmit={d => {
    const file = d.get('file') as File
    if (uploadLimit === undefined) throw new Error('Upload settings are unavailable. Please retry loading them.')
    if (file.size > uploadLimit) throw new Error(`Choose a file no larger than ${uploadLimitText}.`)
    const body = new FormData(); body.append('file', file)
    const params = new URLSearchParams({ subject_id: sid, title: String(d.get('title')), category: String(d.get('category')), visibility: 'private' })
    if (d.get('unit_id')) params.set('unit_id', String(d.get('unit_id')))
    return request('/materials/upload?' + params, { method: 'POST', body })
  }}><SubjectSelect subjects={subjects.data} value={sid} onChange={v => setSid(v)} /><Field label="Unit (optional)"><select key={sid} name="unit_id" defaultValue=""><option value="">Whole subject</option>{units.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}</select></Field><ErrorMessage message={unitError} /><Field label="Material title"><input name="title" required /></Field><Field label="Material category"><select name="category" defaultValue="notes"><option value="notes">Notes</option><option value="assignment">Assignment</option><option value="reference">Reference</option><option value="past-paper">Past paper</option></select></Field><Field label="File"><input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.docx" required /></Field><p className="muted text-sm">PDF, PNG, JPEG or DOCX{uploadLimitText ? ` · Up to ${uploadLimitText}.` : '.'}<br />Uploaded materials are private to your account.</p></AsyncForm> : <Empty><Link className="inline-action" to="/subjects">Create a subject first<Icon name="arrow-right" size={17} /></Link></Empty>}</Panel></div>{deleting && <DeleteMaterialDialog material={deleting} close={() => setDeleting(null)} deleted={() => { setDeleting(null); setMessage('Material deleted.'); materials.reload() }} />}</>
}
function DeleteMaterialDialog({ material, close, deleted }: { material: Material; close: () => void; deleted: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { dialog.current?.showModal() }, [])
  async function remove() {
    setBusy(true); setError('')
    try { await request(`/materials/${material.id}`, { method: 'DELETE' }); deleted() }
    catch (e) { setError((e as Error).message); setBusy(false) }
  }
  return <dialog ref={dialog} className="confirm-dialog" aria-labelledby="delete-material-title" onCancel={event => { event.preventDefault(); if (!busy) close() }}><h2 id="delete-material-title">Delete material?</h2><p>Delete <strong>{material.title}</strong> and its stored file? This action cannot be undone.</p><ErrorMessage message={error} /><div className="button-row"><button className="secondary-button" autoFocus disabled={busy} onClick={close}>Keep material</button><button className="button danger-button" disabled={busy} onClick={() => void remove()}>{busy ? 'Deleting…' : 'Delete material'}</button></div></dialog>
}
function ProfilePage() {
  const { data, loading, error } = useData<Profile>('/profile/me')
  const colleges = useData<{ id: string; name: string }[]>('/colleges')
  const courses = useData<{ id: string; name: string; college_id: string }[]>('/courses')
  const [chosenCollege, setCollege] = useState<string | null>(null)
  const college = chosenCollege ?? data?.college_id ?? ''
  return <><Heading title="Academic profile" subtitle="Set up the details that make this workspace yours." /><ErrorMessage message={error || colleges.error || courses.error} />{loading ? <LoadingState label="Loading profile…" /> : data && <div className="profile-layout"><Panel title="Your academic details"><AsyncForm key={JSON.stringify(data)} label="Save profile" onSubmit={d => post('/profile/me', { academic_year: d.get('academic_year'), semester: Number(d.get('semester')), section: d.get('section'), phone_number: String(d.get('phone_number') || '').trim() || null, college_id: college || null, course_id: d.get('course_id') || null }, 'PUT')}><Field label="Academic year"><input name="academic_year" placeholder="e.g. 2026-27" defaultValue={data.academic_year || ''} required /></Field><Field label="Semester"><input name="semester" type="number" min={1} max={20} defaultValue={data.semester || 1} required /></Field><Field label="Section (optional)"><input name="section" defaultValue={data.section || ''} /></Field><PhoneField defaultValue={data.phone_number || ''} helpId="profile-phone-help" />{!!colleges.data?.length && <Field label="College (optional)"><select value={college} onChange={e => setCollege(e.target.value)}><option value="">Select college</option>{colleges.data.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>}{college && <Field label="Course (optional)"><select key={college} name="course_id" defaultValue={data.course_id || ''}><option value="">Select course</option>{courses.data?.filter(c => c.college_id === college).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>}</AsyncForm></Panel><div className="profile-note"><p className="eyebrow">A FRESH START</p><h2>Your studies.<br />Your space.</h2><p>Once your profile is saved, add a subject and start building your personal library.</p><Link className="button" to="/subjects">Go to subjects<Icon name="arrow-right" size={17} /></Link></div></div>}</>
}

export default function App() {
  return <BrowserRouter><AuthProvider><Routes><Route path="/login" element={<AuthPage />} /><Route path="/register" element={<AuthPage register />} /><Route path="/check-email" element={<CheckEmailPage />} /><Route path="/verify-email" element={<VerifyEmailPage />} /><Route path="/forgot-password" element={<ForgotPasswordPage />} /><Route path="/reset-password" element={<ResetPasswordPage />} /><Route element={<Layout />}><Route index element={<DashboardPage />} /><Route path="subjects" element={<SubjectsPage />} /><Route path="subjects/:id" element={<SubjectPage />} /><Route path="materials" element={<MaterialsPage />} /><Route path="exams" element={<ExamsPage />} /><Route path="exams/calendar" element={<ExamsPage />} /><Route path="notifications" element={<NotificationsPage />} /><Route path="settings/reminders" element={<ReminderSettingsPage />} /><Route path="profile" element={<ProfilePage />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes></AuthProvider></BrowserRouter>
}
