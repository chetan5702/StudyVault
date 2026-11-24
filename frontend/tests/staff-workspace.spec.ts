import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const api = 'http://127.0.0.1:8011'

function samplePdf(): Buffer {
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>', '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>']
  let content = '%PDF-1.4\n'
  const offsets = [0]
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(content)); content += `${index + 1} 0 obj\n${object}\nendobj\n` })
  const start = Buffer.byteLength(content)
  content += 'xref\n0 4\n0000000000 65535 f \n' + offsets.slice(1).map(offset => String(offset).padStart(10, '0') + ' 00000 n \n').join('')
  content += `trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n${start}\n%%EOF\n`
  return Buffer.from(content)
}

async function register(request: APIRequestContext, prefix: string) {
  const response = await request.post(api + '/api/v1/auth/register', {
    data: { full_name: 'Fictional ' + prefix, email: prefix.toLowerCase() + '-' + Date.now() + '@aiml.suh.edu.in', password: 'FictionalPassword123!' },
  })
  expect(response.status()).toBe(201)
  const result = await response.json() as { access_token: string; user: { id: string } }
  return { userId: result.user.id, token: result.access_token, headers: { Authorization: 'Bearer ' + result.access_token } }
}

async function navigateAs(page: Page, token: string, target: string) {
  await page.goto('/login')
  await page.evaluate(() => sessionStorage.clear())
  await page.evaluate(value => sessionStorage.setItem('studyvault.token', value), token)
  await page.goto(target)
}

test('real admin and faculty screens publish only to enrolled fictional students', async ({ page, request }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const admin = await register(request, 'adminbrowser')
  const teacher = await register(request, 'facultybrowser')
  const student = await register(request, 'studentbrowser')
  const outsider = await register(request, 'outsiderbrowser')
  expect((await request.post(api + '/__test__/fixtures/staff-role', {
    data: { user_id: admin.userId, role: 'admin' },
  })).status()).toBe(204)
  const coursesResponse = await request.get(api + '/api/v1/courses', { headers: admin.headers })
  expect(coursesResponse.ok()).toBeTruthy()
  const courses = await coursesResponse.json() as { id: string; name: string }[]
  const selectedCourse = courses.find(c => /artificial intelligence and machine learning/i.test(c.name))
  expect(selectedCourse).toBeTruthy()
  const courseId = selectedCourse!.id

  await navigateAs(page, student.token, '/staff')
  await expect(page.getByText('Staff permissions required')).toBeVisible()
  expect((await request.get(api + '/api/v1/staff/subjects', { headers: student.headers })).status()).toBe(403)

  await navigateAs(page, admin.token, '/staff')
  await expect(page.getByRole('heading', { name: 'Academic administration' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Administration' })).toBeVisible()
  await page.getByLabel('Branch').selectOption(courseId)
  await page.getByLabel('Semester').selectOption('3')
  await page.getByLabel('Subject code').fill('BROWSER331')
  await page.getByLabel('Subject name').fill('Fictional Software Validation')
  await page.getByRole('button', { name: 'Create subject' }).click()
  await expect(page.getByText('Official subject created')).toBeVisible()
  const subjectsResponse = await request.get(api + '/api/v1/staff/subjects', { headers: admin.headers })
  const subjects = await subjectsResponse.json() as { id: string; code: string }[]
  const subject = subjects.find(s => s.code === 'BROWSER331')
  expect(subject).toBeTruthy()

  await page.getByLabel('Verified user ID').fill(teacher.userId)
  await page.getByRole('button', { name: 'Approve faculty' }).click()
  await expect(page.getByText('Faculty account authorized')).toBeVisible()
  await page.getByLabel('Faculty member').selectOption(teacher.userId)
  await page.getByLabel('Academic subject').selectOption(subject!.id)
  await page.getByRole('button', { name: 'Assign faculty' }).click()
  await expect(page.getByText('Teaching assignment created')).toBeVisible()

  await navigateAs(page, outsider.token, '/staff')
  await expect(page.getByText('Staff permissions required')).toBeVisible()
  await navigateAs(page, teacher.token, '/staff')
  await expect(page.getByRole('heading', { name: 'Faculty workspace' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Faculty workspace' })).toBeVisible()
  await expect(page.getByLabel('Assigned subject')).toHaveValue(subject!.id)
  await page.getByLabel('Material title').fill('Fictional Unit One PDF')
  await page.getByLabel('Category').selectOption('notes')
  await page.getByLabel('Unit number (optional)').fill('1')
  await page.getByLabel('Academic session (optional)').fill('2026-27')
  const pdf = samplePdf()
  await page.getByLabel('Document (PDF, PNG, JPEG or DOCX)').setInputFiles({
    name: 'fictional-notes.pdf', mimeType: 'application/pdf', buffer: pdf,
  })
  const uploadResponse = page.waitForResponse(response => response.url().includes('/staff/resources/upload') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Upload draft' }).click()
  const uploaded = await uploadResponse
  expect(uploaded.status(), await uploaded.text()).toBe(201)
  const upload = await uploaded.json() as { id: string; is_published: boolean }
  expect(upload.is_published).toBe(false)
  await expect(page.getByText('Draft uploaded; publish when ready')).toBeVisible()
  await expect(page.getByText('Fictional Unit One PDF')).toBeVisible()
  expect((await request.get(api + '/api/v1/academic/resources', { headers: student.headers })).json()).toBeDefined()

  expect((await request.post(api + '/__test__/fixtures/enrollment', {
    data: { user_id: student.userId, course_id: courseId, semester: 3, academic_session: '2026-27' },
  })).status()).toBe(204)
  await navigateAs(page, student.token, '/academic')
  await expect(page.getByRole('heading', { name: 'Your semester library' })).toBeVisible()
  await expect(page.getByText('Fictional Unit One PDF')).toHaveCount(0)
  expect((await request.get(api + '/api/v1/academic/resources/' + upload.id + '/download', { headers: student.headers })).status()).toBe(404)

  await navigateAs(page, teacher.token, '/staff')
  await page.getByRole('button', { name: /^Publish/ }).click()
  await expect(page.getByText('Resource published')).toBeVisible()
  await navigateAs(page, student.token, '/academic')
  await expect(page.getByText('Fictional Unit One PDF')).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download document' }).click()
  const downloaded = await download
  expect(downloaded.suggestedFilename()).toBe('fictional-notes.pdf')
  expect(await readFile((await downloaded.path())!)).toEqual(pdf)
  const blocked = await request.get(api + '/api/v1/academic/resources/' + upload.id + '/download', { headers: outsider.headers })
  expect(blocked.status()).toBe(404)

  await navigateAs(page, teacher.token, '/staff')
  await page.getByRole('button', { name: /^Unpublish/ }).click()
  await expect(page.getByText('Resource unpublished')).toBeVisible()
  await navigateAs(page, student.token, '/academic')
  await expect(page.getByText('Fictional Unit One PDF')).toHaveCount(0)
  expect((await request.get(api + '/api/v1/academic/resources/' + upload.id + '/download', { headers: student.headers })).status()).toBe(404)
  expect(errors).toEqual([])
})
