import { test, expect } from '@playwright/test'

test('student selects a branch and semester and sees a scoped academic library', async ({ page }) => {
  const email = `academic-${Date.now()}@aiml.suh.edu.in`
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/register')
  await page.getByLabel('Full name').fill('Academic Library Student')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password', { exact: true }).fill('Password123!')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('heading', { name: 'Academic profile' })).toBeVisible()

  await page.getByLabel('University').selectOption({ label: 'Sreenidhi University' })
  await page.getByLabel('Department').selectOption({ label: 'Computer Science and Engineering' })
  await page.getByLabel('Branch / specialization').selectOption({
    label: 'CSE – Artificial Intelligence and Machine Learning',
  })
  await page.getByLabel('Year of study').selectOption('2')
  await expect(page.getByTestId('academic-semester')).toBeVisible()
  await page.getByTestId('academic-semester').selectOption('4')
  await page.getByLabel('Academic session').fill('2026-27')
  await page.getByRole('button', { name: 'Save academic profile' }).click()
  await expect(page.getByText('Academic profile saved.')).toBeVisible()

  await page.getByRole('link', { name: 'Semester library' }).click()
  await expect(page.getByRole('heading', { name: 'Your semester library' })).toBeVisible()
  await expect(page.getByText('Year 2 · Semester 4')).toBeVisible()
  await expect(page.getByText('CSE – Artificial Intelligence and Machine Learning')).toBeVisible()
  await expect(page.getByText(/No curated subjects have been published/)).toBeVisible()

  await page.getByRole('link', { name: 'Edit academic profile' }).click()
  await expect(page.getByLabel('Year of study')).toHaveValue('2')
  await expect(page.getByTestId('academic-semester')).toHaveValue('4')
  await page.getByLabel('Branch / specialization').selectOption({
    label: 'CSE – Data Science',
  })
  await page.getByRole('button', { name: 'Save academic profile' }).click()
  await expect(page.getByText('Academic profile saved.')).toBeVisible()
  await page.getByRole('link', { name: 'Semester library' }).click()
  await expect(page.getByText('CSE – Data Science')).toBeVisible()
  expect(errors).toEqual([])
})
