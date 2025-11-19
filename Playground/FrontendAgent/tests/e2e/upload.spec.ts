import { fileURLToPath } from 'node:url'
import path from 'node:path'
import type { Page } from '@playwright/test'
import { test, expect } from '@playwright/test'

const fixturePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../fixtures/sample.csv',
)

const uploadCsv = async (page: Page) => {
  await page.setInputFiles('input[type="file"]', fixturePath)
  await page.getByLabel('Scenario name').fill('Demo scenario upload')
  await page.getByLabel('Objective').fill('Validate happy path smoke test')
  await page.getByRole('button', { name: /Generate dashboard/i }).click()
}

test.describe('CSV upload flow', () => {
  test('handles upload success path', async ({ page }) => {
    await page.goto('/')
    await uploadCsv(page)

    await expect(page.getByText('CSVProfiler')).toBeVisible()
    await expect(page.getByText('Live Dashboard Preview')).toBeVisible()
  })

  test('shows validation helper when missing file', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Generate dashboard/i }).click()
    await expect(page.getByText('Upload a CSV to get started')).toBeVisible()
  })

  test('allows retry after file-type error', async ({ page }) => {
    await page.goto('/')
    const dummyFile = {
      name: 'notes.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('just text'),
    }
    await page.setInputFiles('input[type="file"]', dummyFile)
    await expect(page.getByText('Please choose a .csv file')).toBeVisible()
    await page.getByRole('button', { name: 'Reset' }).click()
    await expect(page.getByText('Drag & drop or browse for a CSV file')).toBeVisible()
  })
})
