import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { type AcademicResource, type AcademicSubject, type Course, type Department, type Profile } from './api'
import { Empty, ErrorMessage, LoadingState, Panel } from './components'
import { useData } from './hooks'
import { Icon } from './icons'

export function AcademicLibraryPage() {
  const profile = useData<Profile>('/profile/me')
  const courses = useData<Course[]>('/courses')
  const departments = useData<Department[]>('/departments')
  const subjects = useData<AcademicSubject[]>('/academic/subjects')
  const resources = useData<AcademicResource[]>('/academic/resources')
  const [subjectId, setSubjectId] = useState('')
  const [search, setSearch] = useState('')
  const branch = courses.data?.find(c => c.id === profile.data?.course_id)
  const department = departments.data?.find(d => d.id === profile.data?.department_id)
  const currentSubjects = subjects.data || []
  const filteredResources = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (resources.data || []).filter(r =>
      (!subjectId || r.subject_id === subjectId) &&
      (!query || [r.title, r.subject_name, r.category, r.unit_title || '', r.source_label || ''].some(value => value.toLowerCase().includes(query)))
    )
  }, [resources.data, subjectId, search])
  const allLoaded = !profile.loading && !courses.loading && !departments.loading && !subjects.loading && !resources.loading
  const profileReady = !!profile.data?.course_id && !!profile.data?.semester
  const error = profile.error || courses.error || departments.error || subjects.error || resources.error

  return <section className="academic-library">
    <header className="page-heading"><div>
      <p className="eyebrow">STUDYVAULT / ACADEMIC LIBRARY</p>
      <h1>Your semester library</h1>
      <p className="muted">Reviewed academic resources organized by department, branch, semester, subject and unit.</p>
    </div><Link to="/profile" className="secondary-button"><Icon name="edit" size={16} /> Edit academic profile</Link></header>
    <ErrorMessage message={error} />
    {!allLoaded ? <LoadingState label="Loading your academic library…" /> : !profileReady ? <Panel title="Set up your academic context">
      <Empty>Choose a university, department, branch and semester in your academic profile before browsing resources.<p><Link to="/profile" className="inline-action">Complete your profile</Link></p></Empty>
    </Panel> : <>
      <div className="academic-context"><div><small>DEPARTMENT</small><strong>{department?.name || 'Not assigned'}</strong></div>
        <div><small>BRANCH</small><strong>{branch?.name || 'Unknown branch'}</strong></div>
        <div><small>YEAR / SEMESTER</small><strong>Year {profile.data?.year_of_study || Math.ceil((profile.data?.semester || 1) / 2)} · Semester {profile.data?.semester}</strong></div>
        <div><small>ACADEMIC SESSION</small><strong>{profile.data?.academic_year || 'Not selected'}</strong></div>
      </div>
      <p className="muted academic-disclaimer">Semester and branch information is self-reported. Only reviewed and published entries appear here. Your personal uploads and group files stay separate.</p>
      <div className="academic-filters">
        <label>Subject<select value={subjectId} onChange={e => setSubjectId(e.target.value)}><option value="">All semester subjects</option>{currentSubjects.map(s => <option value={s.id} key={s.id}>{s.code} · {s.name}</option>)}</select></label>
        <label>Find a resource<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search notes, unit or question bank" /></label>
      </div>
      {currentSubjects.length === 0 ? <Panel title="Semester subjects"><Empty>No curated subjects have been published for this branch and semester yet. Your personal subjects are still available under <Link to="/subjects">Subjects</Link>.</Empty></Panel> :
      <div className="academic-subject-list">{currentSubjects.filter(s => !subjectId || s.id === subjectId).map(s => {
        const files = filteredResources.filter(r => r.subject_id === s.id)
        return <Panel key={s.id} title={s.code + ' · ' + s.name}>
          {files.length ? <div className="academic-resources">{files.map(resource => {
            const validUrl = /^https:\/\//i.test(resource.url)
            return <article className="academic-resource" key={resource.id}>
              <div><strong>{resource.title}</strong>
                <p className="muted">{resource.unit_number ? 'Unit ' + resource.unit_number + (resource.unit_title ? ' · ' + resource.unit_title : '') : 'Full subject'} · {resource.category}{resource.academic_session ? ' · ' + resource.academic_session : ''}</p>
                {resource.source_label && <small>Source: {resource.source_label}</small>}
              </div>{validUrl ? <a className="secondary-button" href={resource.url} target="_blank" rel="noopener noreferrer">Open resource <Icon name="arrow-right" size={16} /></a> : <small>Unsupported resource link</small>}
            </article>
          })}</div> : <Empty>{search || subjectId ? 'No published resources match these filters.' : 'No published resources for this subject yet.'}</Empty>}
        </Panel>
      })}</div>}
    </>}
  </section>
}
