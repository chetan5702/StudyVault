import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { type AcademicResource, type AcademicSubject, type Course, type Department, type VerifiedEnrollment, downloadAcademicResource } from './api'
import { Empty, ErrorMessage, LoadingState, Panel } from './components'
import { useData } from './hooks'
import { Icon } from './icons'

export function AcademicLibraryPage() {
  const enrollment = useData<VerifiedEnrollment | null>('/academic/enrollment')
  const courses = useData<Course[]>('/courses')
  const departments = useData<Department[]>('/departments')
  const subjects = useData<AcademicSubject[]>('/academic/subjects')
  const resources = useData<AcademicResource[]>('/academic/resources')
  const [subjectId, setSubjectId] = useState('')
  const [search, setSearch] = useState('')
  const [downloadError, setDownloadError] = useState('')
  const branch = courses.data?.find(c => c.id === enrollment.data?.course_id)
  const department = departments.data?.find(d => d.id === branch?.department_id)
  const currentSubjects = subjects.data || []
  const filteredResources = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (resources.data || []).filter(r =>
      (!subjectId || r.subject_id === subjectId) &&
      (!query || [r.title, r.subject_name, r.category, r.unit_title || '', r.source_label || ''].some(value => value.toLowerCase().includes(query)))
    )
  }, [resources.data, subjectId, search])
  const allLoaded = !enrollment.loading && !courses.loading && !departments.loading && !subjects.loading && !resources.loading
  const profileReady = !!enrollment.data
  const error = enrollment.error || courses.error || departments.error || subjects.error || resources.error

  return <section className="academic-library">
    <header className="page-heading"><div>
      <p className="eyebrow">STUDYVAULT / ACADEMIC LIBRARY</p>
      <h1>Your semester library</h1>
      <p className="muted">Approved academic resources filtered by trusted enrollment.</p>
    </div><Link to="/materials" className="secondary-button"><Icon name="files" size={16} /> Personal materials</Link></header>
    <ErrorMessage message={error || downloadError} />
    {!allLoaded ? <LoadingState label="Loading your academic library…" /> : !profileReady ? <Panel title="Awaiting approved academic enrollment">
      <Empty>The official semester library requires approved enrollment. Editing your personal academic profile does not grant access. <Link to="/materials">Your personal materials are still available.</Link></Empty>
    </Panel> : <>
      <div className="academic-context"><div><small>DEPARTMENT</small><strong>{department?.name || 'Not assigned'}</strong></div>
        <div><small>BRANCH</small><strong>{branch?.name || 'Unknown branch'}</strong></div>
        <div><small>YEAR / SEMESTER</small><strong>Year {Math.ceil((enrollment.data?.semester || 1) / 2)} · Semester {enrollment.data?.semester}</strong></div>
        <div><small>ACADEMIC SESSION</small><strong>{enrollment.data?.academic_session || 'Not selected'}</strong></div>
      </div>
      <p className="muted academic-disclaimer">Academic access comes from approved enrollment, not self-reported profile fields. External resource links may have separate access rules.</p>
      <div className="academic-filters">
        <label>Subject<select value={subjectId} onChange={e => setSubjectId(e.target.value)}><option value="">All semester subjects</option>{currentSubjects.map(s => <option value={s.id} key={s.id}>{s.code} · {s.name}</option>)}</select></label>
        <label>Find a resource<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search notes, unit or question bank" /></label>
      </div>
      {currentSubjects.length === 0 ? <Panel title="Semester subjects"><Empty>No curated subjects have been published for this branch and semester yet. Your personal subjects are still available under <Link to="/subjects">Subjects</Link>.</Empty></Panel> :
      <div className="academic-subject-list">{currentSubjects.filter(s => !subjectId || s.id === subjectId).map(s => {
        const files = filteredResources.filter(r => r.subject_id === s.id)
        return <Panel key={s.id} title={s.code + ' · ' + s.name}>
          {files.length ? <div className="academic-resources">{files.map(resource => {
            const validUrl = resource.url ? /^https:\/\//i.test(resource.url) : false
            return <article className="academic-resource" key={resource.id}>
              <div><strong>{resource.title}</strong>
                <p className="muted">{resource.unit_number ? 'Unit ' + resource.unit_number + (resource.unit_title ? ' · ' + resource.unit_title : '') : 'Full subject'} · {resource.category}{resource.academic_session ? ' · ' + resource.academic_session : ''}</p>
                {resource.source_label && <small>Source: {resource.source_label}</small>}
              </div>{resource.download_url ? <button className="secondary-button" onClick={() => { setDownloadError(''); void downloadAcademicResource(resource).catch(e => setDownloadError(e instanceof Error ? e.message : 'Download failed')) }}><Icon name="download" size={16} /> Download document</button> : validUrl ? <a className="secondary-button" href={resource.url || undefined} target="_blank" rel="noopener noreferrer">Open external link <Icon name="arrow-right" size={16} /></a> : <small>Resource unavailable</small>}
            </article>
          })}</div> : <Empty>{search || subjectId ? 'No published resources match these filters.' : 'No published resources for this subject yet.'}</Empty>}
        </Panel>
      })}</div>}
    </>}
  </section>
}
