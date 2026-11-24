import { useState } from 'react'
import { type AcademicSubject, type Course, type FacultyAssignment, type FacultyPerson, type FacultyResource, type StaffRole, post, request, uploadStaffResource } from './api'
import { AsyncForm, Empty, ErrorMessage, Field, LoadingState, Panel } from './components'
import { useData } from './hooks'
import { Icon } from './icons'

export function StaffWorkspacePage() {
  const role = useData<StaffRole>('/staff/me')
  const subjects = useData<AcademicSubject[]>('/staff/subjects')
  const [chosenSubject, setChosenSubject] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const faculty = useData<FacultyPerson[]>(role.data?.role === 'admin' ? '/staff/faculty' : '')
  const assignments = useData<FacultyAssignment[]>(role.data?.role === 'admin' ? '/staff/assignments' : '')
  const programs = useData<Course[]>(role.data?.role === 'admin' ? '/courses' : '')
  const selected = chosenSubject || subjects.data?.[0]?.id || ''
  const resources = useData<FacultyResource[]>(selected && role.data?.role ? '/staff/resources?subject_id=' + encodeURIComponent(selected) : '')
  const roleName = role.data?.role

  async function action(fn: () => Promise<unknown>, label: string) {
    setError('')
    setMessage('')
    try {
      await fn()
      setMessage(label)
      subjects.reload()
      faculty.reload()
      assignments.reload()
      resources.reload()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Action failed'
      setError(msg)
      throw e
    }
  }

  if (role.loading) return <LoadingState label="Checking staff permissions…" />
  if (!roleName) return <Panel title="Staff permissions required"><Empty>This area is restricted to approved faculty and administrators.</Empty></Panel>
  return <section className="academic-library">
    <header className="page-heading"><div><p className="eyebrow">STUDYVAULT / STAFF</p><h1>{roleName === 'admin' ? 'Academic administration' : 'Faculty workspace'}</h1><p className="muted">Official academic subjects and faculty-published study materials.</p></div></header>
    <ErrorMessage message={role.error || error || subjects.error || resources.error} />
    {message && <p role="status" className="success">{message}</p>}
    {roleName === 'admin' && <>
      <Panel title="Create official subject">
        <AsyncForm label="Create subject" resetOnSuccess onSubmit={d => action(() => post('/staff/subjects', {
          course_id: d.get('course_id'), semester: Number(d.get('semester')), code: d.get('code'), name: d.get('name'),
        }), 'Official subject created')}>
          <Field label="Branch"><select name="course_id" required defaultValue=""><option value="">Select branch</option>{(programs.data || []).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
          <Field label="Semester"><select name="semester" defaultValue="1">{[1,2,3,4,5,6,7,8].map(s => <option key={s} value={s}>{s}</option>)}</select></Field>
          <Field label="Subject code"><input name="code" required maxLength={40} /></Field>
          <Field label="Subject name"><input name="name" required maxLength={200} /></Field>
        </AsyncForm>
      </Panel>
      <Panel title="Approve faculty">
        <p className="muted">Faculty must already have a verified account. Confirm their identity before granting permissions.</p>
        <AsyncForm label="Approve faculty" resetOnSuccess onSubmit={d => action(() => post('/staff/faculty', {user_id: d.get('user_id')}), 'Faculty account authorized')}>
          <Field label="Verified user ID"><input name="user_id" required /></Field>
        </AsyncForm>
      </Panel>
      <Panel title="Assign faculty to a subject">
        <AsyncForm label="Assign faculty" onSubmit={d => action(() => post('/staff/assignments', {
          faculty_id: d.get('faculty_id'), subject_id: d.get('subject_id'),
        }), 'Teaching assignment created')}>
          <Field label="Faculty member"><select name="faculty_id" required defaultValue=""><option value="">Select faculty</option>{(faculty.data || []).map(f => <option key={f.id} value={f.id}>{f.full_name} ({f.email})</option>)}</select></Field>
          <Field label="Academic subject"><select name="subject_id" required defaultValue=""><option value="">Select subject</option>{(subjects.data || []).map(s => <option key={s.id} value={s.id}>{s.code} · {s.name}</option>)}</select></Field>
        </AsyncForm>
        {(assignments.data || []).map(a => <article className="academic-resource" key={a.faculty_id + a.subject_id}>
          <span>{(faculty.data || []).find(f => f.id === a.faculty_id)?.full_name || 'Faculty'} — {(subjects.data || []).find(s => s.id === a.subject_id)?.name || 'Subject'}</span>
          <button className="secondary-button" onClick={() => void action(() => request('/staff/assignments/' + encodeURIComponent(a.faculty_id) + '/' + encodeURIComponent(a.subject_id), {method:'DELETE'}), 'Assignment revoked').catch(() => {})}>Revoke</button>
        </article>)}
      </Panel>
    </>}
    <Panel title="Upload and publish official materials">
      {subjects.loading ? <LoadingState label="Loading assigned subjects…" /> : (subjects.data || []).length === 0 ? <Empty>No subjects assigned to this account yet.</Empty> : <>
        <Field label="Assigned subject"><select value={selected} onChange={e => setChosenSubject(e.target.value)}>{(subjects.data || []).map(s => <option key={s.id} value={s.id}>{s.code} · {s.name} (Semester {s.semester})</option>)}</select></Field>
        <AsyncForm label="Upload draft" resetOnSuccess onSubmit={d => action(() => uploadStaffResource(selected, d), 'Draft uploaded; publish when ready')}>
          <Field label="Material title"><input name="title" required maxLength={200}/></Field>
          <Field label="Category"><select name="category" defaultValue="notes"><option value="notes">Notes</option><option value="question-bank">Question bank</option><option value="past-paper">Previous paper</option><option value="syllabus">Syllabus</option><option value="important-questions">Important questions</option></select></Field>
          <Field label="Unit number (optional)"><input type="number" name="unit_number" min={1}/></Field>
          <Field label="Unit title (optional)"><input name="unit_title" maxLength={200}/></Field>
          <Field label="Academic session (optional)"><input name="academic_session" maxLength={20} placeholder="2026-27"/></Field>
          <Field label="Document (PDF, PNG, JPEG or DOCX)"><input type="file" name="file" required accept=".pdf,.png,.jpg,.jpeg,.docx"/></Field>
        </AsyncForm>
        {(resources.data || []).map(r => <article className="academic-resource" key={r.id}>
          <div><strong>{r.title}</strong><p className="muted">{r.file_name || 'External resource'} · {r.is_published ? 'Published' : 'Draft'}</p></div>
          {r.file_name && <button className="secondary-button" onClick={() => void action(() => post('/staff/resources/' + r.id + '/publish', {is_published: !r.is_published}, 'PATCH'), r.is_published ? 'Resource unpublished' : 'Resource published').catch(() => {})}>{r.is_published ? 'Unpublish' : 'Publish'} <Icon name="check" size={16}/></button>}
          {r.file_name && <button className="secondary-button" onClick={() => { if (window.confirm('Permanently delete this document?')) void action(() => request('/staff/resources/' + r.id, {method:'DELETE'}), 'Resource deleted').catch(() => {}) }}>Delete</button>}
        </article>)}
      </>}
    </Panel>
  </section>
}
