import { expect, test, type APIRequestContext } from '@playwright/test'

function pdfBuffer() {
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>', '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>']
  let text = '%PDF-1.4\n'
  const offsets = [0]
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(text)); text += `${index + 1} 0 obj\n${object}\nendobj\n` })
  const xref = Buffer.byteLength(text)
  text += 'xref\n0 4\n0000000000 65535 f \n' + offsets.slice(1).map(value => `${String(value).padStart(10, '0')} 00000 n \n`).join('')
  return Buffer.from(`${text}trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`)
}

const pngBuffer = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
const docxBuffer = Buffer.from('UEsDBBQAAAAAAP2tTl26tvkp3QAAAN0AAAATAAAAW0NvbnRlbnRfVHlwZXNdLnhtbDxUeXBlcyB4bWxucz0iaHR0cDovL3NjaGVtYXMub3BlbnhtbGZvcm1hdHMub3JnL3BhY2thZ2UvMjAwNi9jb250ZW50LXR5cGVzIj48T3ZlcnJpZGUgUGFydE5hbWU9Ii93b3JkL2RvY3VtZW50LnhtbCIgQ29udGVudFR5cGU9ImFwcGxpY2F0aW9uL3ZuZC5vcGVueG1sZm9ybWF0cy1vZmZpY2Vkb2N1bWVudC53b3JkcHJvY2Vzc2luZ21sLmRvY3VtZW50Lm1haW4reG1sIiAvPjwvVHlwZXM+UEsDBBQAAAAAAP2tTl32kku1agAAAGoAAAARAAAAd29yZC9kb2N1bWVudC54bWw8dzpkb2N1bWVudCB4bWxuczp3PSJodHRwOi8vc2NoZW1hcy5vcGVueG1sZm9ybWF0cy5vcmcvd29yZHByb2Nlc3NpbmdtbC8yMDA2L21haW4iPjx3OmJvZHkgLz48L3c6ZG9jdW1lbnQ+UEsBAhQAFAAAAAAA/a1OXbq2+SndAAAA3QAAABMAAAAAAAAAAAAAAIABAAAAAFtDb250ZW50X1R5cGVzXS54bWxQSwECFAAUAAAAAAD9rU5d9pJLtWoAAABqAAAAEQAAAAAAAAAAAAAAgAEOAQAAd29yZC9kb2N1bWVudC54bWxQSwUGAAAAAAIAAgCAAAAApwEAAAAA', 'base64')

async function uploadMaterial(request: APIRequestContext, headers: Record<string, string>, subjectId: string, title: string, name: string, mimeType: string, buffer: Buffer) {
  const query = new URLSearchParams({ subject_id: subjectId, title, category: 'notes', visibility: 'private' })
  const response = await request.post(`/api/v1/materials/upload?${query}`, { headers, multipart: { file: { name, mimeType, buffer } } })
  expect(response.status(), await response.text()).toBe(201)
}

test('realistic crowded content stays readable on desktop and mobile', async ({ page }, testInfo) => {
  const registered = await page.request.post('/api/v1/auth/register', {
    data: { full_name: 'Responsive Layout Student', email: `visual-${Date.now()}@example.com`, password: 'Password123!' },
  })
  expect(registered.status()).toBe(201)
  const { access_token: token } = await registered.json()
  const headers = { Authorization: `Bearer ${token}` }
  const createdSubject = await page.request.post('/api/v1/subjects', {
    headers,
    data: { code: 'CSE-LONG-401', name: 'Advanced Distributed Systems and Resilient Cloud Architecture', semester: 7 },
  })
  expect(createdSubject.status()).toBe(201)
  const subject = await createdSubject.json()

  await uploadMaterial(page.request, headers, subject.id, 'Architecture diagram', 'distributed-system-architecture.png', 'image/png', pngBuffer)
  await uploadMaterial(page.request, headers, subject.id, 'Project research brief', 'semester-project-research-brief.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', docxBuffer)
  const longFileName = 'fault-tolerance-consensus-replication-and-disaster-recovery-complete-semester-reference-notes.pdf'
  const longMaterialTitle = 'Fault tolerance, consensus, replication and disaster recovery — complete semester reference notes'
  await uploadMaterial(page.request, headers, subject.id, longMaterialTitle, longFileName, 'application/pdf', pdfBuffer())

  const examTitles = [
    'Distributed consensus algorithms comprehensive midterm examination',
    'Cloud infrastructure security laboratory practical',
    'Fault tolerant systems design review',
    'Research methodology presentation and viva',
    'Advanced networking weekly assessment',
    'End semester resilient architecture examination',
  ]
  for (const [index, title] of examTitles.entries()) {
    const response = await page.request.post('/api/v1/exams', {
      headers,
      data: {
        subject_id: subject.id,
        title,
        exam_type: index === examTitles.length - 1 ? 'final' : 'assessment',
        scheduled_for: new Date(Date.now() + (index + 2) * 86_400_000).toISOString(),
        location: `Academic block ${index + 1}, examination hall with a deliberately long location name`,
        timezone: 'Asia/Kolkata',
      },
    })
    expect(response.status(), await response.text()).toBe(201)
  }

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/login')
  await page.evaluate(value => sessionStorage.setItem('studyvault.token', value), token)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expect(page.locator('.deadline-row')).toHaveCount(4)
  await expect(page.getByText(longMaterialTitle, { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: /Add a subject/ })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('desktop-crowded-dashboard.png'), fullPage: true })

  await page.goto('/materials')
  await expect(page.getByLabel('PDF file')).toBeVisible()
  await expect(page.getByLabel('IMG file')).toBeVisible()
  await expect(page.getByLabel('DOCX file')).toBeVisible()
  await expect(page.getByText(longFileName, { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  await page.goto('/exams')
  await expect(page.locator('[data-testid="exam-row"]')).toHaveCount(6)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expect(page.locator('.deadline-row')).toHaveCount(4)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('mobile-crowded-dashboard.png'), fullPage: true })

  await page.goto('/materials')
  await expect(page.getByText(longFileName, { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('mobile-long-materials.png'), fullPage: true })
})
