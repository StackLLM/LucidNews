import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// WCAG 2.x contrast of the colour pairs the interface really uses, in both themes.
// The tokens are read from styles.css, so a changed colour is checked without touching this test.
const css = readFileSync(resolve(process.cwd(), 'src/styles.css'), 'utf8')

function tokens(block: string): Record<string, string> {
  return Object.fromEntries([...block.matchAll(/--color-([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)].map((m) => [m[1], m[2]]))
}

const light = tokens(css.slice(css.indexOf('@theme'), css.indexOf('/* Dialog entrances')))
const dark = { ...light, ...tokens(css.slice(css.indexOf("html[data-theme='dark']"), css.indexOf('@layer base'))) }

type Rgb = [number, number, number]
const rgb = (hex: string): Rgb => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as Rgb
const mix = (top: Rgb, bottom: Rgb, alpha: number): Rgb => top.map((v, i) => v * alpha + bottom[i] * (1 - alpha)) as Rgb
const luminance = (c: Rgb) => {
  const [r, g, b] = c.map((v) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const ratio = (a: Rgb, b: Rgb) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** [foreground token, alpha, background token, background tint (token, alpha) or none, minimum ratio, why] */
type Pair = [string, number, string, [string, number] | null, number, string]
const TEXT = 4.5
const UI = 3 // large text, icons and component borders
const pairs: Pair[] = [
  ['ink', 1, 'canvas', null, TEXT, 'body text on the page'],
  ['ink', 1, 'surface', null, TEXT, 'text on a card'],
  ['ink', 0.7, 'surface', null, TEXT, 'secondary text (text-ink/70)'],
  ['ink', 0.7, 'canvas', null, TEXT, 'secondary text on the page'],
  ['muted', 1, 'canvas', null, TEXT, 'muted text on the page'],
  ['muted', 1, 'surface', null, TEXT, 'muted text on a card'],
  ['faint', 1, 'canvas', null, TEXT, 'placeholders and captions on the page'],
  ['faint', 1, 'surface', null, TEXT, 'placeholders and captions on a card'],
  ['accent', 1, 'canvas', null, TEXT, 'links on the page'],
  ['accent', 1, 'surface', null, TEXT, 'links on a card'],
  ['accent', 1, 'accent-soft', null, TEXT, 'accent chips'],
  ['on-fill', 1, 'accent', null, TEXT, 'primary button'],
  ['on-fill', 1, 'accent-deep', null, TEXT, 'primary button on hover / hero end'],
  ['on-fill', 1, 'ink', null, TEXT, 'dark pill (critical, preview)'],
  ['on-fill', 1, 'rumor', null, TEXT, 'alert fill'],
  ['on-fill', 0.75, 'accent', null, TEXT, 'hero secondary text'],
  ['confirmed', 1, 'surface', ['confirmed', 0.1], TEXT, 'reliability badge: confirmed'],
  ['reliable', 1, 'surface', ['reliable', 0.1], TEXT, 'reliability badge: reliable'],
  ['unverified', 1, 'surface', ['unverified', 0.1], TEXT, 'reliability badge: unverified'],
  ['rumor', 1, 'surface', ['rumor', 0.1], TEXT, 'reliability badge: rumor'],
  ['failing', 1, 'surface', null, TEXT, 'failing source'],
  ['confirmed', 1, 'canvas', null, TEXT, 'status text on the page'],
  ['rumor', 1, 'canvas', null, TEXT, 'error text on the page'],
  ['accent', 1, 'canvas', null, UI, 'focus ring and active tab'],
  ['series-selected', 1, 'surface', null, UI, 'chart bars (selected)'],
  ['series-collected', 1, 'surface', null, UI, 'chart bars (collected)'],
]

describe.each([
  ['light', light],
  ['dark', dark],
])('contrast, %s theme', (_name, theme) => {
  it.each(pairs)('%s (%d) on %s — %s', (fg, alpha, bg, tint, minimum, why) => {
    let background = rgb(theme[bg])
    if (tint) background = mix(rgb(theme[tint[0]]), background, tint[1])
    const foreground = mix(rgb(theme[fg]), background, alpha)
    expect(ratio(foreground, background), why).toBeGreaterThanOrEqual(minimum)
  })
})

it('declares every token of the light theme in the dark theme', () => {
  const darkOnly = tokens(css.slice(css.indexOf("html[data-theme='dark']"), css.indexOf('@layer base')))
  for (const name of Object.keys(light)) expect(Object.keys(darkOnly), name).toContain(name)
})
