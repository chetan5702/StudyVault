import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { post, request, type Exam, type Subject } from './api'
import { AsyncForm, Countdown, Empty, ErrorMessage, Field, LoadingState, Panel } from './components'
import { formatExamDate, localDateCandidates, localInputDate, localTimezone, timezoneOffsetLabel } from './dates'
import { useData } from './hooks'
import { Icon } from './icons'

export function ExamsPage() {
  const exams = useData<Exam[]>('/exams')
  const subjects = useData<Subject[]>('/subjects')
  const [subjectFilter, setSubjectFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('upcoming')
  const [editing, setEditing] = useState<Exam | null>(null)
  const [deleting, setDeleting] = useState<Exam | null>(null)
  const [message, setMessage] = useState('')
  const [formVersion, setFormVersion] = useState(0)
  const [now, setNow] = useState(Date.now)
  const editor = useRef<HTMLDivElement>(null)
  const calendarView = useLocation().pathname.endsWith('/calendar')
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(timer) }, [])
  const all = [...(exams.data || [])].sort((a, b) => Date.parse(a.scheduled_for) - Date.parse(b.scheduled_for))
  const upcoming = all.filter(exam => Date.parse(exam.scheduled_for) > now)
  const filtered = all.filter(exam => (!subjectFilter || exam.subject_id === subjectFilter) && (statusFilter === 'all' || (Date.parse(exam.scheduled_for) > now ? statusFilter === 'upcoming' : statusFilter === 'completed')))
  const nextExam = upcoming.find(exam => !subjectFilter || exam.subject_id === subjectFilter)
  const startEdit = (exam: Exam) => {
    setEditing(exam); setMessage('')
    editor.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  function saved() {
    setMessage(editing ? 'Exam updated. Pending reminders have been updated.' : 'Exam scheduled. Your reminder preferences are applied.')
    setEditing(null); setFormVersion(value => value + 1); exams.reload()
  }
  return <>
    <div className="page-heading"><div><p className="eyebrow">STUDYVAULT / WORKSPACE</p><h1>{calendarView ? 'Exam calendar' : 'Exam schedule'}</h1><p className="muted">See what’s ahead and give yourself time to prepare.</p></div><Link className="secondary-button" to="/settings/reminders"><Icon name="bell" size={17} />Reminder settings</Link></div>
    <ErrorMessage message={exams.error || subjects.error} />
    {message && <p role="status" className="success action-notice">{message}</p>}
    <div className="exam-summary"><div><p className="eyebrow">YOUR NEXT MILESTONE</p>{nextExam ? <><strong>{nextExam.title}</strong><p>{formatExamDate(nextExam.scheduled_for)} · {localTimezone()}</p><Countdown date={nextExam.scheduled_for} /></> : <><strong>A clear calendar, a fresh start.</strong><p>Schedule an exam to start your countdown.</p></>}</div><div className="exam-summary-count"><strong>{upcoming.length}</strong><span>upcoming {upcoming.length === 1 ? 'exam' : 'exams'}</span></div></div>
    <div className="exam-layout"><Panel><div className="section-toolbar"><h2>Your exams</h2><div className="view-switch" aria-label="Exam view"><NavLink end to="/exams">List view</NavLink><NavLink to="/exams/calendar">Calendar view</NavLink></div></div>
      <div className="exam-filters"><Field label="Filter by subject"><select value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)}><option value="">All subjects</option>{subjects.data?.map(subject => <option key={subject.id} value={subject.id}>{subject.code} · {subject.name}</option>)}</select></Field><Field label="Exam status"><select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="upcoming">Upcoming</option><option value="completed">Completed</option><option value="all">All exams</option></select></Field></div>
      <p className="calendar-timezone">All dates and times shown in {localTimezone()}.</p>
      {exams.loading ? <LoadingState label="Loading exams…" /> : calendarView ? <ExamCalendar exams={filtered} subjects={subjects.data || []} now={now} edit={startEdit} remove={setDeleting} /> : filtered.length ? <div>{(statusFilter === 'completed' ? [...filtered].reverse() : filtered).map(exam => <ExamRow key={exam.id} exam={exam} subjects={subjects.data || []} now={now} edit={startEdit} remove={setDeleting} />)}</div> : <Empty>{!all.length ? 'No exams scheduled. Add an exam to see it here and on your dashboard.' : 'No exams match these filters.'}</Empty>}
    </Panel><div className="exam-editor" ref={editor}><Panel title={editing ? 'Edit examination' : 'Schedule an exam'}>{subjects.data?.length ? <ExamForm key={`${editing?.id || 'new'}-${formVersion}`} exam={editing} subjects={subjects.data} saved={saved} cancel={() => setEditing(null)} /> : <Empty><Link className="inline-action" to="/subjects">Create a subject first<Icon name="arrow-right" size={17} /></Link></Empty>}</Panel></div></div>
    {deleting && <DeleteExamDialog exam={deleting} close={() => setDeleting(null)} deleted={() => { if (editing?.id === deleting.id) setEditing(null); setDeleting(null); setMessage('Exam deleted. Pending reminders have been cancelled.'); exams.reload() }} />}
  </>
}

function ExamRow({ exam, subjects, now, edit, remove }: { exam: Exam; subjects: Subject[]; now: number; edit: (exam: Exam) => void; remove: (exam: Exam) => void }) {
  const completed = Date.parse(exam.scheduled_for) <= now
  return <article className={`exam-row ${completed ? 'is-completed' : ''}`} data-testid="exam-row"><div className="exam-row-heading"><div><h3>{exam.title}</h3><p className="muted">{subjects.find(subject => subject.id === exam.subject_id)?.name}</p></div>{completed && <span className="tag">Completed</span>}</div>{!completed && <Countdown date={exam.scheduled_for} />}<p>{formatExamDate(exam.scheduled_for)}</p>{exam.location && <small>{exam.location}</small>}<div className="button-row exam-actions"><button className="secondary-button" onClick={() => edit(exam)} aria-label={`Edit ${exam.title}`}><Icon name="edit" size={16} />Edit / reschedule</button><button className="text-button danger-text" onClick={() => remove(exam)} aria-label={`Delete ${exam.title}`}><Icon name="trash" size={16} />Delete</button></div></article>
}

function ExamForm({ exam, subjects, saved, cancel }: { exam: Exam | null; subjects: Subject[]; saved: () => void; cancel: () => void }) {
  const initialDate = exam ? localInputDate(exam.scheduled_for) : ''
  const [subject, setSubject] = useState(exam?.subject_id || '')
  const [date, setDate] = useState(initialDate)
  const initialCandidates = localDateCandidates(initialDate)
  const [occurrence, setOccurrence] = useState(exam && initialCandidates.length > 1 ? String(initialCandidates.findIndex(candidate => Math.floor(candidate.getTime() / 60_000) === Math.floor(Date.parse(exam.scheduled_for) / 60_000))) : '')
  const candidates = localDateCandidates(date)
  const originalOccurrence = initialCandidates.findIndex(candidate => exam && Math.floor(candidate.getTime() / 60_000) === Math.floor(Date.parse(exam.scheduled_for) / 60_000))
  return <AsyncForm label={exam ? 'Save exam changes' : 'Schedule exam'} onSuccess={saved} onSubmit={data => {
    if (!candidates.length) throw new Error('This local time does not exist in your timezone because the clocks change. Choose a different time.')
    if (candidates.length > 1 && occurrence === '') throw new Error('This local time occurs twice. Choose which occurrence you mean.')
    const unchanged = exam && initialDate === date && (candidates.length === 1 || Number(occurrence) === originalOccurrence)
    const scheduled = unchanged ? exam.scheduled_for : candidates[Number(occurrence) || 0].toISOString()
    return post(exam ? `/exams/${exam.id}` : '/exams', { title: data.get('title'), subject_id: subject, exam_type: data.get('exam_type'), scheduled_for: scheduled, timezone: unchanged ? exam.timezone : localTimezone(), location: data.get('location') || null }, exam ? 'PATCH' : 'POST')
  }}>
    <Field label="Subject"><select name="subject_id" value={subject} onChange={e => setSubject(e.target.value)} required><option value="">Select a subject</option>{subjects.map(value => <option key={value.id} value={value.id}>{value.code} · {value.name}</option>)}</select></Field>
    <Field label="Exam title"><input name="title" defaultValue={exam?.title || ''} required maxLength={200} placeholder="e.g. First midterm" /></Field>
    <Field label="Exam type"><input name="exam_type" list="exam-types" defaultValue={exam?.exam_type || 'midterm'} required maxLength={60} /><datalist id="exam-types"><option value="midterm" /><option value="final" /><option value="quiz" /><option value="practical" /></datalist></Field>
    <Field label="Date and time (your local time)"><input name="date" type="datetime-local" value={date} onChange={e => { setDate(e.target.value); setOccurrence('') }} required /></Field>
    <p className="muted text-sm">Timezone: {localTimezone()}. Reminders will follow this exam time.</p>
    {date && !candidates.length && <ErrorMessage message="This time does not exist locally because the clocks change. Choose another time." />}
    {candidates.length > 1 && <Field label="Repeated local time"><select value={occurrence} onChange={e => setOccurrence(e.target.value)} required><option value="">Choose a clock occurrence</option>{candidates.map((candidate, index) => <option key={candidate.toISOString()} value={String(index)}>{index === 0 ? 'First' : 'Second'} occurrence ({timezoneOffsetLabel(candidate)})</option>)}</select><span className="muted">The clocks turn back on this date. Select the intended occurrence.</span></Field>}
    <Field label="Location (optional)"><input name="location" maxLength={300} defaultValue={exam?.location || ''} /></Field>
    {exam && <button type="button" className="secondary-button" onClick={cancel}>Cancel editing</button>}
  </AsyncForm>
}

function ExamCalendar({ exams, subjects, now, edit, remove }: { exams: Exam[]; subjects: Subject[]; now: number; edit: (exam: Exam) => void; remove: (exam: Exam) => void }) {
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1))
  const [selected, setSelected] = useState(() => localInputDate(new Date()).slice(0, 10))
  const firstDay = (month.getDay() + 6) % 7
  const dayCount = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
  const dayKey = (day: number) => localInputDate(new Date(month.getFullYear(), month.getMonth(), day)).slice(0, 10)
  const days = Array.from({ length: Math.ceil((firstDay + dayCount) / 7) * 7 }, (_, index) => index - firstDay + 1)
  const selectedExams = exams.filter(exam => localInputDate(exam.scheduled_for).slice(0, 10) === selected)
  const title = month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  function moveMonth(amount: number) {
    const next = new Date(month.getFullYear(), month.getMonth() + amount, 1)
    setMonth(next); setSelected(localInputDate(next).slice(0, 10))
  }
  return <div className="exam-calendar"><div className="section-toolbar calendar-toolbar"><h3 aria-live="polite">{title}</h3><div className="button-row"><button className="secondary-button icon-button" aria-label="Previous month" onClick={() => moveMonth(-1)}><Icon name="arrow-left" size={17} /></button><button className="secondary-button" onClick={() => { const today = new Date(); setMonth(new Date(today.getFullYear(), today.getMonth(), 1)); setSelected(localInputDate(today).slice(0, 10)) }}>Today</button><button className="secondary-button icon-button" aria-label="Next month" onClick={() => moveMonth(1)}><Icon name="arrow-right" size={17} /></button></div></div>
    <div className="calendar-grid" aria-label={title}>{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => <div className="calendar-weekday" key={day}>{day}</div>)}{days.map(day => {
      if (day < 1 || day > dayCount) return <div className="calendar-blank" key={day} />
      const key = dayKey(day)
      const count = exams.filter(exam => localInputDate(exam.scheduled_for).slice(0, 10) === key).length
      return <button key={day} className={`calendar-day ${selected === key ? 'is-selected' : ''} ${key === localInputDate(new Date(now)).slice(0, 10) ? 'is-today' : ''}`} aria-label={`${key}, ${count} ${count === 1 ? 'exam' : 'exams'}`} aria-pressed={selected === key} onClick={() => setSelected(key)}><span>{day}</span>{count > 0 && <span className="calendar-exam-count">{count}<span className="calendar-count-word"> {count === 1 ? 'exam' : 'exams'}</span></span>}</button>
    })}</div>
    <div className="calendar-agenda"><h3>{new Date(`${selected}T12:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</h3>{selectedExams.length ? selectedExams.map(exam => <ExamRow key={exam.id} exam={exam} subjects={subjects} now={now} edit={edit} remove={remove} />) : <Empty>No exams on this date with the current filters.</Empty>}</div>
  </div>
}

function DeleteExamDialog({ exam, close, deleted }: { exam: Exam; close: () => void; deleted: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { dialog.current?.showModal() }, [])
  async function remove() {
    setBusy(true); setError('')
    try { await request(`/exams/${exam.id}`, { method: 'DELETE' }); deleted() }
    catch (e) { setError((e as Error).message); setBusy(false) }
  }
  return <dialog ref={dialog} className="confirm-dialog" aria-labelledby="delete-exam-title" onCancel={event => { event.preventDefault(); if (!busy) close() }}><h2 id="delete-exam-title">Delete examination?</h2><p>Delete <strong>{exam.title}</strong> from your schedule? All pending reminders for this exam will be cancelled.</p><ErrorMessage message={error} /><div className="button-row"><button className="secondary-button" autoFocus disabled={busy} onClick={close}>Keep exam</button><button className="button danger-button" disabled={busy} onClick={() => void remove()}>{busy ? 'Deleting…' : 'Delete exam'}</button></div></dialog>
}
