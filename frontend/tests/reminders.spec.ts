import { test, expect, type Page } from '@playwright/test'

test.use({ timezoneId: 'Asia/Kolkata' })

async function prepareStudent(page: Page, prefix: string) {
  const account = await page.request.post('/api/v1/auth/register', {
    data: { full_name: 'Reminder Student', email: `${prefix}-${Date.now()}@example.com`, password: 'Password123!' },
  })
  expect(account.status()).toBe(201)
  const { access_token: token } = await account.json()
  const headers = { Authorization: `Bearer ${token}` }
  const subjectResponse = await page.request.post('/api/v1/subjects', { headers, data: { code: 'EX101', name: 'Examination Science' } })
  expect(subjectResponse.status()).toBe(201)
  const subject = await subjectResponse.json()
  await page.goto('/login')
  await page.evaluate(value => sessionStorage.setItem('studyvault.token', value), token)
  await page.goto('/exams')
  return { headers, subject }
}

async function localInput(page: Page, instant: string) {
  return page.evaluate(value => {
    const date = new Date(value)
    return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
  }, instant)
}

async function runWorker(page: Page, now: string) {
  const response = await page.request.post('http://127.0.0.1:8011/__test__/reminders/run', { data: { now } })
  expect(response.status(), await response.text()).toBe(200)
}

test('exam management, scheduled worker delivery, notification privacy and mobile calendar', async ({ page }, testInfo) => {
  const { headers, subject } = await prepareStudent(page, 'reminders')
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/settings/reminders')
  await page.getByLabel('In-app notifications').check()
  await page.getByLabel('7 days before', { exact: true }).uncheck()
  await page.getByLabel('3 days before', { exact: true }).uncheck()
  await page.getByLabel('1 day before', { exact: true }).check()
  await page.getByLabel('1 hour before', { exact: true }).check()
  await page.getByLabel('Notification timezone').fill('Asia/Kolkata')
  await page.getByRole('button', { name: 'Save reminder preferences' }).click()
  await expect(page.getByText('Saved successfully.')).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('7 days before', { exact: true })).not.toBeChecked()
  await expect(page.getByLabel('1 day before', { exact: true })).toBeChecked()

  await page.goto('/exams')
  await page.getByRole('combobox', { name: 'Subject', exact: true }).selectOption(subject.id)
  await page.getByLabel('Exam title').fill('Reminder Midterm')
  const originalDate = new Date(Date.now() + 10 * 86_400_000)
  originalDate.setSeconds(0, 0)
  await page.getByLabel('Date and time (your local time)').fill(await localInput(page, originalDate.toISOString()))
  await page.getByLabel('Location (optional)').fill('Room 12')
  const creating = page.waitForResponse(response => response.url().endsWith('/exams') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Schedule exam', exact: true }).click()
  const createResponse = await creating
  expect(createResponse.status()).toBe(201)
  const exam = await createResponse.json()
  expect(Date.parse(exam.scheduled_for)).toBe(originalDate.getTime())
  await expect(page.getByTestId('exam-row')).toHaveCount(1)
  await expect(page.getByTestId('exam-row').locator('.countdown')).toContainText('remaining')

  await page.getByRole('button', { name: 'Edit Reminder Midterm', exact: true }).click()
  await expect(page.getByLabel('Date and time (your local time)')).toHaveValue(await localInput(page, originalDate.toISOString()))
  const revisedDate = new Date(originalDate.getTime() + 2 * 86_400_000)
  await page.getByLabel('Exam title').fill('Rescheduled Midterm')
  await page.getByLabel('Date and time (your local time)').fill(await localInput(page, revisedDate.toISOString()))
  await page.getByLabel('Location (optional)').fill('Room 24')
  const updating = page.waitForResponse(response => response.url().endsWith(`/exams/${exam.id}`) && response.request().method() === 'PATCH')
  await page.getByRole('button', { name: 'Save exam changes' }).click()
  expect(Date.parse((await (await updating).json()).scheduled_for)).toBe(revisedDate.getTime())
  await expect(page.getByTestId('exam-row')).toContainText('Room 24')
  await page.reload()
  await expect(page.getByTestId('exam-row')).toContainText('Rescheduled Midterm')

  const past = await page.request.post('/api/v1/exams', { headers, data: { subject_id: subject.id, title: 'Completed Final', scheduled_for: new Date(Date.now() - 86_400_000).toISOString() } })
  expect(past.status()).toBe(201)
  const other = await page.request.post('/api/v1/subjects', { headers, data: { code: 'EX102', name: 'Other Subject' } })
  const otherSubject = await other.json()
  await page.goto('/exams')
  await expect(page.getByRole('heading', { name: 'Exam schedule', exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: 'Exam status', exact: true }).selectOption('completed')
  await expect(page.getByTestId('exam-row')).toContainText('Completed Final')
  await page.getByRole('combobox', { name: 'Exam status', exact: true }).selectOption('all')
  await expect(page.getByTestId('exam-row')).toHaveCount(2)
  await page.getByRole('combobox', { name: 'Filter by subject', exact: true }).selectOption(otherSubject.id)
  await expect(page.getByTestId('exam-row')).toHaveCount(0)
  await page.getByRole('combobox', { name: 'Filter by subject', exact: true }).selectOption(subject.id)
  await page.getByRole('combobox', { name: 'Exam status', exact: true }).selectOption('upcoming')
  await page.getByRole('link', { name: 'Calendar view', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Exam calendar', exact: true })).toBeVisible()
  const targetLocal = await localInput(page, revisedDate.toISOString())
  const todayLocal = await localInput(page, new Date().toISOString())
  const monthSteps = (Number(targetLocal.slice(0, 4)) - Number(todayLocal.slice(0, 4))) * 12 + Number(targetLocal.slice(5, 7)) - Number(todayLocal.slice(5, 7))
  for (let index = 0; index < monthSteps; index++) await page.getByRole('button', { name: 'Next month', exact: true }).click()
  await page.getByRole('button', { name: `${targetLocal.slice(0, 10)}, 1 exam`, exact: true }).click()
  await expect(page.getByTestId('exam-row')).toContainText('Rescheduled Midterm')
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('mobile-exam-calendar.png'), fullPage: true })
  await page.setViewportSize({ width: 1280, height: 900 })

  // Old scheduling instant must not deliver any cancelled reminder after rescheduling.
  await runWorker(page, new Date(originalDate.getTime() - 60 * 60_000 + 1000).toISOString())
  expect((await (await page.request.get('/api/v1/notifications', { headers })).json()).items).toHaveLength(0)
  const deliveryTime = new Date(revisedDate.getTime() - 86_400_000 + 1000).toISOString()
  await runWorker(page, deliveryTime)
  await page.goto('/notifications')
  await page.getByRole('button', { name: 'Refresh notifications' }).click()
  await expect(page.getByRole('link', { name: 'Notifications, 1 unread', exact: true })).toBeVisible()
  await expect(page.getByTestId('notification-item')).toHaveCount(1)
  await expect(page.getByTestId('notification-item')).toContainText('Rescheduled Midterm')
  await page.getByRole('button', { name: 'Mark as read', exact: true }).click()
  await expect(page.getByText('0 unread', { exact: true })).toBeVisible()
  await runWorker(page, deliveryTime)
  await page.reload()
  await expect(page.getByTestId('notification-item')).toHaveCount(1)
  await expect(page.getByText('0 unread', { exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('notification-center.png'), fullPage: true })

  await page.goto('/exams')
  await page.getByRole('button', { name: 'Delete Rescheduled Midterm', exact: true }).click()
  await page.getByRole('button', { name: 'Keep exam', exact: true }).click()
  await expect(page.getByTestId('exam-row')).toHaveCount(1)
  await page.getByRole('button', { name: 'Delete Rescheduled Midterm', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Delete exam', exact: true }).click()
  await expect(page.getByTestId('exam-row')).toHaveCount(0)
  await runWorker(page, new Date(revisedDate.getTime() - 60 * 60_000 + 1000).toISOString())
  expect((await (await page.request.get('/api/v1/notifications', { headers })).json()).items).toHaveLength(1)

  await page.getByRole('button', { name: 'Log out' }).click()
  await prepareStudent(page, 'private-reminders')
  await page.goto('/notifications')
  await expect(page.getByTestId('notification-item')).toHaveCount(0)
  await expect(page.getByText('0 unread', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('local exam entry rejects a daylight-saving gap and distinguishes a repeated hour', async ({ browser }) => {
  const context = await browser.newContext({ timezoneId: 'America/New_York', baseURL: 'http://127.0.0.1:5174' })
  const page = await context.newPage()
  try {
    const { subject } = await prepareStudent(page, 'daylight')
    await page.getByRole('combobox', { name: 'Subject', exact: true }).selectOption(subject.id)
    await page.getByLabel('Exam title').fill('DST Examination')
    await page.getByLabel('Date and time (your local time)').fill('2030-03-10T02:30')
    await page.getByRole('button', { name: 'Schedule exam', exact: true }).click()
    await expect(page.getByRole('alert').last()).toContainText('does not exist')
    await expect(page.getByTestId('exam-row')).toHaveCount(0)
    await page.getByLabel('Date and time (your local time)').fill('2030-11-03T01:30')
    await page.getByRole('combobox', { name: 'Repeated local time' }).selectOption('1')
    const created = page.waitForResponse(response => response.url().endsWith('/exams') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Schedule exam', exact: true }).click()
    const response = await created
    expect(response.status()).toBe(201)
    expect(Date.parse((await response.json()).scheduled_for)).toBe(Date.parse('2030-11-03T06:30:00Z'))
    await page.getByRole('button', { name: 'Edit DST Examination', exact: true }).click()
    await expect(page.getByRole('combobox', { name: 'Repeated local time' })).toHaveValue('1')
  } finally { await context.close() }
})
