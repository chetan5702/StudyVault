import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const api = 'http://127.0.0.1:8011/api/v1'

function pdfBuffer() {
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>', '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>']
  let text = '%PDF-1.4\n'
  const offsets = [0]
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(text)); text += `${index + 1} 0 obj\n${object}\nendobj\n` })
  const xref = Buffer.byteLength(text)
  text += 'xref\n0 4\n0000000000 65535 f \n' + offsets.slice(1).map(offset => String(offset).padStart(10, '0') + ' 00000 n \n').join('')
  text += `trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`
  return Buffer.from(text)
}

async function createWorkspace(request: APIRequestContext, label: string) {
  const registered = await request.post(`${api}/auth/register`, {
    data: {
      full_name: 'Unit Material Student',
      email: `${label}-${Date.now()}@example.com`,
      password: 'Password123!',
    },
  })
  expect(registered.status()).toBe(201)
  const token = (await registered.json()).access_token as string
  const headers = { Authorization: `Bearer ${token}` }
  const createdSubject = await request.post(`${api}/subjects`, {
    headers,
    data: { code: 'WEB201', name: 'Web Systems', semester: 2 },
  })
  expect(createdSubject.status()).toBe(201)
  const subject = await createdSubject.json() as { id: string }
  return { token, headers, subjectId: subject.id }
}

async function createUnit(
  request: APIRequestContext,
  headers: Record<string, string>,
  subjectId: string,
  name: string,
  orderIndex: number,
) {
  const response = await request.post(`${api}/subjects/${subjectId}/units`, {
    headers,
    data: { subject_id: subjectId, name, order_index: orderIndex },
  })
  expect(response.status()).toBe(201)
  return await response.json() as { id: string }
}

async function uploadMaterial(
  request: APIRequestContext,
  headers: Record<string, string>,
  subjectId: string,
  title: string,
  category: string,
  unitId?: string,
) {
  const params = new URLSearchParams({
    subject_id: subjectId,
    title,
    category,
    visibility: 'private',
  })
  if (unitId) params.set('unit_id', unitId)
  const response = await request.post(`${api}/materials/upload?${params}`, {
    headers,
    multipart: {
      file: { name: `${category}.pdf`, mimeType: 'application/pdf', buffer: pdfBuffer() },
    },
  })
  expect(response.status()).toBe(201)
}

async function openAuthenticated(page: Page, token: string, path: string) {
  await page.addInitScript(value => sessionStorage.setItem('studyvault.token', value), token)
  await page.goto(path)
}

test('edits units, protects linked units, and deletes empty units', async ({ page, request }) => {
  const workspace = await createWorkspace(request, 'unit-controls')
  const unit = await createUnit(request, workspace.headers, workspace.subjectId, 'Introduction', 1)
  await createUnit(request, workspace.headers, workspace.subjectId, 'Temporary Unit', 2)
  await uploadMaterial(
    request,
    workspace.headers,
    workspace.subjectId,
    'Core PDF notes',
    'notes',
    unit.id,
  )
  await openAuthenticated(page, workspace.token, `/subjects/${workspace.subjectId}`)

  await page.getByRole('button', { name: 'Edit Introduction' }).click()
  await page.getByLabel('Unit name').fill('Foundations')
  const unitUpdated = page.waitForResponse(response => response.url().includes('/units/') && response.request().method() === 'PATCH')
  await page.getByRole('button', { name: 'Save unit changes' }).click()
  expect((await unitUpdated).status()).toBe(200)
  await expect(page.getByText('Foundations', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Delete Foundations' }).click()
  const linkedDelete = page.waitForResponse(response => response.url().includes('/units/') && response.request().method() === 'DELETE')
  await page.getByRole('button', { name: 'Delete unit', exact: true }).click()
  expect((await linkedDelete).status()).toBe(409)
  await expect(page.getByRole('alert')).toContainText(/material/i)
  await page.getByRole('button', { name: 'Keep unit' }).click()

  await page.getByRole('button', { name: 'Delete Temporary Unit' }).click()
  const emptyDelete = page.waitForResponse(response => response.url().includes('/units/') && response.request().method() === 'DELETE')
  await page.getByRole('button', { name: 'Delete unit', exact: true }).click()
  expect((await emptyDelete).status()).toBe(204)
  await expect(page.getByText('Temporary Unit', { exact: true })).toHaveCount(0)

  await page.getByRole('link', { name: /View this subject.*materials/ }).click()
  await expect(page).toHaveURL(new RegExp(`/materials\\?subject_id=${workspace.subjectId}`))
  await expect(page.getByLabel('Filter by subject')).toHaveValue(workspace.subjectId)
})

test('combines material filters and confirms owner deletion', async ({ page, request }) => {
  const workspace = await createWorkspace(request, 'material-controls')
  await uploadMaterial(request, workspace.headers, workspace.subjectId, 'Core PDF notes', 'notes')
  await uploadMaterial(request, workspace.headers, workspace.subjectId, 'Delete me PDF', 'assignment')
  await openAuthenticated(page, workspace.token, `/materials?subject_id=${workspace.subjectId}`)

  await expect(page.getByLabel('Filter by subject')).toHaveValue(workspace.subjectId)
  await page.getByLabel('Search materials').fill('Core PDF')
  await page.getByRole('combobox', { name: 'Category', exact: true }).selectOption('notes')
  const combinedFilter = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname.endsWith('/materials')
      && url.searchParams.get('search') === 'Core PDF'
      && url.searchParams.get('category') === 'notes'
      && url.searchParams.get('subject_id') === workspace.subjectId
  })
  await page.getByRole('button', { name: 'Apply filters' }).click()
  expect((await combinedFilter).status()).toBe(200)
  await expect(page.getByRole('heading', { name: 'Core PDF notes' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Delete me PDF' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Clear filters' }).click()
  await page.getByRole('combobox', { name: 'Category', exact: true }).selectOption('assignment')
  const categoryFilter = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname.endsWith('/materials') && url.searchParams.get('category') === 'assignment'
  })
  await page.getByRole('button', { name: 'Apply filters' }).click()
  expect((await categoryFilter).status()).toBe(200)
  await expect(page.getByRole('heading', { name: 'Delete me PDF' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Core PDF notes' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Delete Delete me PDF' }).click()
  await expect(page.getByRole('heading', { name: 'Delete material?' })).toBeVisible()
  const materialDelete = page.waitForResponse(response => response.url().includes('/materials/') && response.request().method() === 'DELETE')
  await page.getByRole('button', { name: 'Delete material', exact: true }).click()
  expect((await materialDelete).status()).toBe(200)
  await expect(page.getByText('No materials match these filters.')).toBeVisible()
})
