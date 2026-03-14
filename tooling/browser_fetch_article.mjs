#!/usr/bin/env node

import fs from 'node:fs'
import process from 'node:process'

import { chromium } from 'playwright-core'

const USER_AGENT =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'

const DEFAULT_TIMEOUT_MS = Number.parseInt(process.env.PRISM_BROWSER_FETCH_TIMEOUT_MS || '15000', 10)
const DEFAULT_WAIT_MS = Number.parseInt(process.env.PRISM_BROWSER_FETCH_RENDER_WAIT_MS || '2500', 10)

function resolveExecutablePath() {
  const candidates = [
    process.env.PRISM_BROWSER_EXECUTABLE,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  ].filter(Boolean)

  for (const candidate of candidates) {
    try {
      fs.accessSync(candidate, fs.constants.X_OK)
      return candidate
    } catch {
      // continue
    }
  }

  return null
}

async function main() {
  const url = process.argv[2]
  if (!url) {
    console.error(JSON.stringify({ error: 'missing_url' }))
    process.exit(64)
  }

  const executablePath = resolveExecutablePath()
  if (!executablePath) {
    console.error(JSON.stringify({ error: 'browser_unavailable' }))
    process.exit(2)
  }

  const browser = await chromium.launch({
    executablePath,
    headless: true,
    args: ['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage'],
  })

  try {
    const context = await browser.newContext({
      userAgent: USER_AGENT,
      locale: 'en-US',
      timezoneId: 'America/Denver',
      viewport: { width: 1440, height: 2200 },
    })
    const page = await context.newPage()
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
      })
    })

    page.setDefaultNavigationTimeout(DEFAULT_TIMEOUT_MS)
    page.setDefaultTimeout(DEFAULT_TIMEOUT_MS)

    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: DEFAULT_TIMEOUT_MS })
    await Promise.race([
      page
        .waitForSelector(
          'article p, [itemprop="articleBody"] p, main p, .article-body p, .entry-content p',
          { timeout: Math.min(5000, DEFAULT_TIMEOUT_MS) },
        )
        .catch(() => null),
      page.waitForTimeout(DEFAULT_WAIT_MS),
    ])
    await page.waitForLoadState('networkidle', { timeout: 3000 }).catch(() => null)

    const html = await page.content()
    const title = await page.title().catch(() => '')

    process.stdout.write(
      JSON.stringify({
        executablePath,
        finalUrl: page.url(),
        html,
        title,
      }),
    )
  } finally {
    await browser.close()
  }
}

main().catch((error) => {
  console.error(
    JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
    }),
  )
  process.exit(1)
})
