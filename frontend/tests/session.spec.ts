import { test, expect, type Page, type Route } from '@playwright/test'

async function prepareStudent(page: Page, prefix: string) {
  const response = await page.request.post('/api/v1/auth/register', {
    data: { full_name: 'Session Student', email: `${prefix}-${Date.now()}@example.com`, password: 'Password123!' },
  })
  expect(response.status()).toBe(201)
  const { access_token: token } = await response.json()
  await page.goto('/login')
  await page.evaluate(value => sessionStorage.setItem('studyvault.token', value), token)
  return { Authorization: `Bearer ${token}` }
}

for (const operation of ['request', 'download'] as const) {
  for (const changedSession of [true, false]) {
    test(`${operation}: ${changedSession ? 'a late 401 preserves a newer session' : 'a current 401 clears the expired session'}`, async ({ page }) => {
      await page.goto('/login')
      await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeVisible()
      await page.evaluate(() => {
        sessionStorage.setItem('studyvault.token', 'earlier-session')
        sessionStorage.setItem('test.unauthorized-events', '0')
        window.addEventListener('studyvault:unauthorized', () => {
          sessionStorage.setItem('test.unauthorized-events', String(Number(sessionStorage.getItem('test.unauthorized-events')) + 1))
        })
      })
      let receiveRoute!: (route: Route) => void
      const received = new Promise<Route>(resolve => { receiveRoute = resolve })
      await page.route(operation === 'request' ? '**/api/v1/session-probe' : '**/api/v1/materials/session-probe/download', route => receiveRoute(route))
      const pending = page.evaluate(async kind => {
        // Load the same API client used by the UI, and hold its actual HTTP response.
        const modulePath = '/src/api.ts'
        const api = await import(modulePath)
        try {
          if (kind === 'request') await api.request('/session-probe')
          else await api.download({ id: 'session-probe', file_name: 'notes.pdf' })
          return 'unexpected success'
        } catch (error) { return (error as Error).message }
      }, operation)
      const held = await received
      expect(held.request().headers().authorization).toBe('Bearer earlier-session')
      if (changedSession) await page.evaluate(() => sessionStorage.setItem('studyvault.token', 'newer-session'))
      await held.fulfill({ status: 401, json: { detail: 'Session expired' } })
      expect(await pending).not.toBe('unexpected success')
      expect(await page.evaluate(() => sessionStorage.getItem('studyvault.token'))).toBe(changedSession ? 'newer-session' : null)
      expect(await page.evaluate(() => sessionStorage.getItem('test.unauthorized-events'))).toBe(changedSession ? '0' : '1')
    })
  }
}

test('dashboard advances to the next exam when time passes and refreshes on focus', async ({ page }) => {
  await prepareStudent(page, 'dashboard-refresh')
  const start = new Date('2034-04-05T10:00:00Z')
  await page.clock.install({ time: start })
  let phase = 0
  let loads = 0
  const examTitles = ['First exam', 'Following exam', 'Updated while away']
  const scheduledFor = () => new Date(start.getTime() + (phase === 0 ? 60_000 : 3_600_000)).toISOString()
  await page.route('**/api/v1/dashboard', route => {
    loads++
    return route.fulfill({ json: {
      welcome: 'Session Student',
      stats: { subjects: 1, materials: 0, upcoming_exams: phase === 0 ? 2 : 1, pending_tasks: 0 },
      next_exam: { title: examTitles[phase], subject: 'Mathematics', scheduled_for: scheduledFor() },
      recent_materials: [],
    } })
  })
  await page.route('**/api/v1/exams?status=upcoming', route => route.fulfill({ json: [{
    id: `exam-${phase}`,
    title: examTitles[phase],
    subject_id: 'mathematics',
    exam_type: 'midterm',
    scheduled_for: scheduledFor(),
    location: null,
    timezone: 'UTC',
  }] }))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'First exam', exact: true })).toBeVisible()
  const initialLoads = loads
  phase = 1
  await page.clock.runFor(61_000)
  await expect(page.getByRole('heading', { name: 'Following exam', exact: true })).toBeVisible()
  expect(loads).toBeGreaterThan(initialLoads)
  await expect(page.locator('.overview-strip > div').nth(2).locator('strong')).toHaveText('1')
  phase = 2
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect(page.getByRole('heading', { name: 'Updated while away', exact: true })).toBeVisible()
})

test('material uploads display and enforce the backend configured limit', async ({ page }) => {
  const headers = await prepareStudent(page, 'upload-limit')
  const created = await page.request.post('/api/v1/subjects', { headers, data: { code: 'LIM101', name: 'Upload limits' } })
  expect(created.status()).toBe(201)
  const subject = await created.json()
  await page.route('**/api/v1/materials/config', route => route.fulfill({ json: { max_upload_size_bytes: 1024 } }))
  let uploads = 0
  await page.route('**/api/v1/materials/upload?*', route => {
    uploads++
    return route.fulfill({ status: 201, json: { id: 'boundary-upload' } })
  })
  await page.goto('/materials')
  await expect(page.getByText(/Up to .*1,024 bytes/)).toBeVisible()
  await page.getByRole('combobox', { name: 'Subject', exact: true }).selectOption(subject.id)
  await page.getByLabel('Material title').fill('Size boundary')
  await page.getByLabel('File', { exact: true }).setInputFiles({ name: 'notes.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(1025) })
  await page.getByRole('button', { name: 'Upload material', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('no larger than')
  expect(uploads).toBe(0)
  await page.getByLabel('File', { exact: true }).setInputFiles({ name: 'notes.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(1024) })
  await page.getByRole('button', { name: 'Upload material', exact: true }).click()
  await expect(page.getByText('Saved successfully.')).toBeVisible()
  expect(uploads).toBe(1)
})

test('unavailable upload settings can be retried without sending a file', async ({ page }) => {
  const headers = await prepareStudent(page, 'upload-config-retry')
  const created = await page.request.post('/api/v1/subjects', { headers, data: { code: 'CFG101', name: 'Upload configuration' } })
  expect(created.status()).toBe(201)
  let available = false
  await page.route('**/api/v1/materials/config', route => available
    ? route.fulfill({ json: { max_upload_size_bytes: 4096 } })
    : route.fulfill({ status: 503, json: { detail: 'Upload settings temporarily unavailable' } }))
  await page.goto('/materials')
  await expect(page.getByRole('alert')).toContainText('temporarily unavailable')
  await expect(page.getByRole('button', { name: 'Upload material', exact: true })).toHaveCount(0)
  available = true
  await page.getByRole('button', { name: 'Retry upload settings', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Upload material', exact: true })).toBeVisible()
  await expect(page.getByText(/Up to .*4,096 bytes/)).toBeVisible()
})

test('collapsed mobile navigation is absent from keyboard order and accessible links', async ({ page }) => {
  await prepareStudent(page, 'mobile-navigation')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  const toggle = page.getByRole('button', { name: 'Toggle navigation', exact: true })
  await expect(toggle).toBeVisible()
  await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toHaveCount(0)
  await expect(page.locator('#workspace-navigation')).toBeHidden()
  await toggle.focus()
  await page.keyboard.press('Shift+Tab')
  expect(await page.evaluate(() => !!document.activeElement?.closest('#workspace-navigation'))).toBe(false)
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Subjects', exact: true }).click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toHaveCount(0)
  await page.setViewportSize({ width: 1280, height: 900 })
  await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toBeVisible()
})
