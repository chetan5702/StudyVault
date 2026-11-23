export type User = { id: string; email: string; full_name: string }
export type Subject = { id: string; code: string; name: string; semester: number | null }
export type Unit = { id: string; subject_id: string; name: string; order_index: number }
export type Profile = { academic_year: string | null; year_of_study: number | null; semester: number | null; section: string | null; phone_number: string | null; college_id: string | null; department_id: string | null; course_id: string | null }
export type Department = { id: string; college_id: string; code: string; name: string }
export type Course = { id: string; college_id: string; department_id: string | null; name: string; degree: string | null }
export type VerifiedEnrollment = { course_id: string; semester: number; academic_session: string; verification_source: 'university' | 'admin' | 'development'; verified_at: string }
export type AcademicSubject = { id: string; course_id: string; semester: number; code: string; name: string }
export type AcademicResource = { id: string; subject_id: string; subject_code: string; subject_name: string; semester: number; title: string; url: string | null; file_name: string | null; download_url: string | null; category: string; source_label: string | null; unit_number: number | null; unit_title: string | null; academic_session: string | null }
export type Material = { id: string; user_id: string; title: string; file_name: string; size_bytes: number; mime_type: string; subject_id: string; unit_id: string | null; category: string; visibility: string; created_at: string }
export type Exam = { id: string; title: string; subject_id: string; exam_type: string; scheduled_for: string; location: string | null; timezone: string }
export type Notification = { id: string; exam_id: string | null; title: string; message: string; scheduled_for: string; delivered_at: string | null; read_at: string | null }
export type NotificationList = { items: Notification[]; unread_count: number }
export type ReminderPreferences = { in_app_enabled: boolean; email_enabled: boolean; reminder_minutes: number[]; timezone: string; email_available: boolean }
export type RecentMaterial = Pick<Material, 'id' | 'title' | 'category' | 'file_name' | 'mime_type'> & { created_at: string | null }
export type Dashboard = { welcome: string; stats: { subjects: number; materials: number; upcoming_exams: number; pending_tasks: number }; next_exam: { title: string; subject: string; scheduled_for: string } | null; recent_materials: RecentMaterial[]; pending_tasks: { id: string; title: string; completed: boolean; due_date: string | null }[] }
export type AuthResult = {
  access_token: string | null
  token_type: 'bearer'
  user: User
  verification_required: boolean
}
const base = import.meta.env.VITE_API_URL || '/api/v1'
export const session = {
  token: () => sessionStorage.getItem('studyvault.token'),
  set: (token: string) => sessionStorage.setItem('studyvault.token', token),
  clear: () => sessionStorage.removeItem('studyvault.token'),
}
function expireSession(requestToken: string | null) {
  // A response from an earlier account must not clear a newer sign-in.
  if (requestToken && session.token() === requestToken) {
    session.clear()
    window.dispatchEvent(new Event('studyvault:unauthorized'))
  }
}
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = session.token()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(base + path, { ...options, headers })
  if (response.status === 401) expireSession(token)
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map((e: { msg: string }) => e.msg).join('; ') : `Request failed (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
export function post<T>(path: string, body: unknown, method = 'POST') {
  return request<T>(path, { method, body: JSON.stringify(body) })
}
export async function download(material: Material) {
  const token = session.token()
  const response = await fetch(`${base}/materials/${material.id}/download`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!response.ok) {
    if (response.status === 401) expireSession(token)
    throw new Error('Unable to download this material. Please check your session and access.')
  }
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url; anchor.download = material.file_name; anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}


export type StaffRole = { role: 'admin' | 'faculty' | null }
export type FacultyPerson = { id: string; full_name: string; email: string }
export type FacultyAssignment = { faculty_id: string; subject_id: string }
export type FacultyResource = { id: string; subject_id: string; title: string; category: string; unit_number: number | null; unit_title: string | null; academic_session: string | null; is_published: boolean; file_name: string | null; size_bytes: number | null }

export async function uploadStaffResource(subjectId: string, fields: FormData): Promise<FacultyResource> {
  const params = new URLSearchParams()
  params.set('subject_id', subjectId)
  for (const name of ['title', 'category', 'unit_number', 'unit_title', 'academic_session']) {
    const field = fields.get(name)
    if (field && String(field).trim()) params.set(name, String(field).trim())
  }
  const file = fields.get('file')
  if (!(file instanceof File) || file.size === 0) throw new Error('Select a document to upload.')
  const body = new FormData()
  body.set('file', file)
  return request<FacultyResource>('/staff/resources/upload?' + params, { method: 'POST', body })
}

export async function downloadAcademicResource(resource: AcademicResource): Promise<void> {
  if (!resource.download_url || !resource.file_name) throw new Error('Resource is not downloadable.')
  const token = session.token()
  const response = await fetch(base + resource.download_url, {
    headers: token ? { Authorization: 'Bearer ' + token } : {},
  })
  if (response.status === 401) expireSession(token)
  if (!response.ok) throw new Error('Resource access denied or file unavailable.')
  const url = URL.createObjectURL(await response.blob())
  try {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = resource.file_name
    anchor.click()
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}
