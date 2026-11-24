import { test, expect } from '@playwright/test'

const user = { id: 'verified-user', email: 'student@aiml.suh.edu.in', full_name: 'Student User' }

test('registration and login handle verification-required responses', async ({ page }) => {
  await page.route('**/api/v1/auth/register', route => route.fulfill({
    status: 201,
    contentType: 'application/json',
    body: JSON.stringify({ access_token: null, token_type: 'bearer', user, verification_required: true }),
  }))
  await page.goto('/register')
  await page.getByLabel('Full name').fill(user.full_name)
  await page.getByLabel('Email address').fill(user.email)
  await page.getByLabel('Password', { exact: true }).fill('Password123!')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL(`/check-email?email=${encodeURIComponent(user.email)}`)
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible()
  await expect(page.getByLabel('Email address')).toHaveValue(user.email)
  expect(await page.evaluate(() => sessionStorage.getItem('studyvault.token'))).toBeNull()

  await page.route('**/api/v1/auth/login', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ access_token: null, token_type: 'bearer', user, verification_required: true }),
  }))
  await page.goto('/login')
  await page.getByLabel('Email address').fill(user.email)
  await page.getByLabel('Password', { exact: true }).fill('Password123!')
  await page.getByRole('button', { name: 'Log in', exact: true }).click()
  await expect(page).toHaveURL(`/check-email?email=${encodeURIComponent(user.email)}`)
  expect(await page.evaluate(() => sessionStorage.getItem('studyvault.token'))).toBeNull()
})

test('resend verification, password request, and password reset use the public account routes', async ({ page }) => {
  await page.route('**/api/v1/auth/resend-verification', async route => {
    expect(route.request().postDataJSON()).toEqual({ email: user.email })
    await route.fulfill({ json: { message: 'If the account exists, a verification email has been sent.' } })
  })
  await page.goto(`/check-email?email=${encodeURIComponent(user.email)}`)
  await page.getByRole('button', { name: 'Send another verification email' }).click()
  await expect(page.getByRole('status')).toContainText('verification email has been sent')

  await page.route('**/api/v1/auth/request-password-reset', async route => {
    expect(route.request().postDataJSON()).toEqual({ email: user.email })
    await route.fulfill({ json: { message: 'If the account exists, a password reset email has been sent.' } })
  })
  await page.goto('/forgot-password')
  await page.getByLabel('Email address').fill(user.email)
  await page.getByRole('button', { name: 'Send reset link' }).click()
  await expect(page.getByRole('status')).toContainText('password reset email has been sent')

  await page.goto('/reset-password?token=reset-token')
  await page.getByLabel('New password', { exact: true }).fill('NewPassword123!')
  await page.getByLabel('Confirm new password').fill('different-password')
  await page.getByRole('button', { name: 'Update password' }).click()
  await expect(page.getByText('Passwords do not match.')).toBeVisible()

  await page.route('**/api/v1/auth/confirm-password-reset', async route => {
    expect(route.request().postDataJSON()).toEqual({ token: 'reset-token', new_password: 'NewPassword123!' })
    await route.fulfill({ json: { message: 'Your password has been reset.' } })
  })
  await page.getByLabel('Confirm new password').fill('NewPassword123!')
  await page.getByRole('button', { name: 'Update password' }).click()
  await expect(page).toHaveURL('/reset-password')
  await expect(page.getByRole('heading', { name: 'Password updated' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Log in with your new password' })).toBeVisible()
})

test('verification link exchanges its token and starts the verified session', async ({ page }) => {
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/auth/verify-email')) {
      expect(route.request().postDataJSON()).toEqual({ token: 'verification-token' })
      await route.fulfill({ json: { access_token: 'verified-session', token_type: 'bearer', user, verification_required: false } })
    } else if (path.endsWith('/profile/me')) {
      await route.fulfill({ json: { academic_year: null, semester: null, section: null, phone_number: null, college_id: null, course_id: null } })
    } else if (path.endsWith('/colleges') || path.endsWith('/courses')) {
      await route.fulfill({ json: [] })
    } else if (path.endsWith('/notifications')) {
      await route.fulfill({ json: { items: [], unread_count: 0 } })
    } else if (path.endsWith('/staff/me')) {
      // Newly logged-in mocked student has no staff role. Without this mock
      // the real API correctly rejects the fake bearer token with 401,
      // which ends the synthetic browser session.
      await route.fulfill({ json: { role: null } })
    } else {
      await route.continue()
    }
  })
  await page.goto('/verify-email?token=verification-token')
  await expect(page).toHaveURL('/profile')
  await expect(page.getByRole('heading', { name: 'Academic profile' })).toBeVisible()
  expect(await page.evaluate(() => sessionStorage.getItem('studyvault.token'))).toBe('verified-session')
})

test('password visibility toggle keeps the typed value on login and registration', async ({ page }) => {
  for (const url of ['/login', '/register']) {
    await page.goto(url)
    const input = page.getByLabel('Password', { exact: true })
    await input.fill('TypedPassword123!')
    await expect(input).toHaveAttribute('type', 'password')
    await page.getByRole('button', { name: 'Show password' }).click()
    await expect(input).toHaveAttribute('type', 'text')
    await expect(input).toHaveValue('TypedPassword123!')
    await page.getByRole('button', { name: 'Hide password' }).click()
    await expect(input).toHaveAttribute('type', 'password')
    await expect(input).toHaveValue('TypedPassword123!')
  }
})

test('password reset controls can reveal fields independently', async ({ page }) => {
  await page.goto('/reset-password?token=example')
  const current = page.getByLabel('New password', { exact: true })
  const confirmation = page.getByLabel('Confirm new password')
  await current.fill('NewPassword123!')
  await confirmation.fill('NewPassword123!')
  await page.getByRole('button', { name: 'Show new password', exact: true }).click()
  await expect(current).toHaveAttribute('type', 'text')
  await expect(confirmation).toHaveAttribute('type', 'password')
  await expect(current).toHaveValue('NewPassword123!')
  await page.getByRole('button', { name: 'Show confirm new password' }).click()
  await expect(confirmation).toHaveAttribute('type', 'text')
  await expect(confirmation).toHaveValue('NewPassword123!')
})
