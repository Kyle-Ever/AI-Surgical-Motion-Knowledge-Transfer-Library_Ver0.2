import { Page } from '@playwright/test'

// ── Title Card ──────────────────────────────────────────────
interface TitleCardOpts {
  bg?: string
  titleColor?: string
  subtitleColor?: string
}

export async function blankIntro(page: Page, bg = '#0a0a0a') {
  await page.goto('about:blank')
  await page.evaluate((bg) => {
    document.body.style.cssText = `margin:0;background:${bg};`
  }, bg)
  await page.waitForTimeout(400)
}

export async function titleCard(
  page: Page,
  title: string,
  subtitle: string,
  ms = 3500,
  opts: TitleCardOpts = {}
) {
  const bg = opts.bg || 'linear-gradient(135deg, #0a0a0a, #0f172a, #0a0a0a)'
  const titleColor = opts.titleColor || 'color:#60a5fa;'
  const subtitleColor = opts.subtitleColor || 'color:#94a3b8;'

  await page.evaluate(
    ({ title, subtitle, bg, titleColor, subtitleColor }) => {
      // Remove any existing title card
      document.getElementById('sc-title-card')?.remove()

      const card = document.createElement('div')
      card.id = 'sc-title-card'
      card.style.cssText = `
        position:fixed;inset:0;z-index:99999;
        display:flex;flex-direction:column;align-items:center;justify-content:center;
        background:${bg};
        opacity:0;transition:opacity 0.8s ease;
      `
      card.innerHTML = `
        <h1 style="font-size:3.2rem;font-weight:800;margin:0;letter-spacing:-0.02em;${titleColor}">${title}</h1>
        <p style="font-size:1.3rem;margin:0.6rem 0 0;font-weight:400;${subtitleColor}">${subtitle}</p>
      `
      document.body.appendChild(card)

      // Fade in
      requestAnimationFrame(() => {
        card.style.opacity = '1'
      })
    },
    { title, subtitle, bg, titleColor, subtitleColor }
  )

  // Hold
  await page.waitForTimeout(ms - 1600)

  // Fade out
  await page.evaluate(() => {
    const card = document.getElementById('sc-title-card')
    if (card) card.style.opacity = '0'
  })
  await page.waitForTimeout(800)

  // Remove
  await page.evaluate(() => {
    document.getElementById('sc-title-card')?.remove()
  })
}

// ── Subtitle Overlay ────────────────────────────────────────
export async function initOverlays(page: Page) {
  await page.evaluate(() => {
    // Remove existing
    document.getElementById('sc-subtitle')?.remove()

    const sub = document.createElement('div')
    sub.id = 'sc-subtitle'
    sub.style.cssText = `
      position:fixed;bottom:48px;left:50%;transform:translateX(-50%);
      z-index:99998;
      background:rgba(0,0,0,0.78);
      color:#fff;font-size:1.1rem;font-weight:500;
      padding:10px 28px;border-radius:8px;
      opacity:0;transition:opacity 0.4s ease;
      pointer-events:none;white-space:nowrap;
      max-width:90vw;text-align:center;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      box-shadow:0 4px 20px rgba(0,0,0,0.3);
    `
    document.body.appendChild(sub)
  })
}

export async function sub(page: Page, text: string, ms = 3000) {
  await page.evaluate(
    ({ text }) => {
      const el = document.getElementById('sc-subtitle')
      if (el) {
        el.textContent = text
        el.style.opacity = '1'
      }
    },
    { text }
  )
  await page.waitForTimeout(ms)
  await page.evaluate(() => {
    const el = document.getElementById('sc-subtitle')
    if (el) el.style.opacity = '0'
  })
  await page.waitForTimeout(400)
}

export async function subPersist(page: Page, text: string) {
  await page.evaluate(
    ({ text }) => {
      const el = document.getElementById('sc-subtitle')
      if (el) {
        el.textContent = text
        el.style.opacity = '1'
      }
    },
    { text }
  )
}

export async function hideSub(page: Page) {
  await page.evaluate(() => {
    const el = document.getElementById('sc-subtitle')
    if (el) el.style.opacity = '0'
  })
  await page.waitForTimeout(400)
}

// ── Smooth Scroll ───────────────────────────────────────────
export async function smoothScroll(
  page: Page,
  selector: string,
  stepPx = 250,
  delayMs = 800
) {
  await page.evaluate(
    async ({ selector, stepPx, delayMs }) => {
      const el = document.querySelector(selector) as HTMLElement
      if (!el) return
      const maxScroll = el.scrollHeight - el.clientHeight
      while (el.scrollTop < maxScroll) {
        el.scrollBy({ top: stepPx, behavior: 'smooth' })
        await new Promise((r) => setTimeout(r, delayMs))
      }
    },
    { selector, stepPx, delayMs }
  )
}

export async function smoothScrollPage(
  page: Page,
  stepPx = 250,
  delayMs = 800
) {
  await page.evaluate(
    async ({ stepPx, delayMs }) => {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight
      while (window.scrollY < maxScroll - 10) {
        window.scrollBy({ top: stepPx, behavior: 'smooth' })
        await new Promise((r) => setTimeout(r, delayMs))
      }
    },
    { stepPx, delayMs }
  )
}

export async function smoothScrollIframe(
  page: Page,
  iframeTitle: string,
  stepPx = 250,
  delayMs = 800
) {
  const frame = page.frameLocator(`iframe[title="${iframeTitle}"]`)
  await frame.locator('body').evaluate(
    async (body, { stepPx, delayMs }) => {
      const maxScroll = body.scrollHeight - body.clientHeight
      while (body.scrollTop < maxScroll - 10) {
        body.scrollBy({ top: stepPx, behavior: 'smooth' })
        await new Promise((r) => setTimeout(r, delayMs))
      }
    },
    { stepPx, delayMs }
  )
}
