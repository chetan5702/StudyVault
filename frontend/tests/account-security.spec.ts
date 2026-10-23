import { test, expect } from '@playwright/test'

const user = { id: 'verified-user', email: 'student@example.com', full_name: 'Student User' }

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
    } else {
      await route.continue()
    }
  })
  await page.goto('/verify-email?token=verification-token')
  await expect(page).toHaveURL('/profile')
  await expect(page.getByRole('heading', { name: 'Academic profile' })).toBeVisible()
  expect(await page.evaluate(() => sessionStorage.getItem('studyvault.token'))).toBe('verified-session')
})
