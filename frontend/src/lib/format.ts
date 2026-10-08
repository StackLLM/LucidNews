import type { Language } from './i18n'

const locales: Record<Language, string> = { en: 'en-GB', fr: 'fr-FR' }

export function formatEditionDate(iso: string, language: Language): string {
  return new Intl.DateTimeFormat(locales[language], {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(iso))
}

export function formatItemTime(iso: string, language: Language): string {
  return new Intl.DateTimeFormat(locales[language], {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}

export function formatScore(score: number | null): string {
  return score === null ? '–' : score.toFixed(1)
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

const sourceNames: Record<string, string> = {
  hackernews: 'Hacker News',
  rss: 'RSS',
  github: 'GitHub',
  reddit: 'Reddit',
  telegram: 'Telegram',
  twitter: 'X',
  gdelt: 'GDELT',
}

export function sourceName(type: string): string {
  return sourceNames[type] ?? type
}

export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Local calendar day, used to group runs: `2026-10-06`. */
export function dayKey(value: Date | string): string {
  const date = typeof value === 'string' ? new Date(value) : value
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function formatTime(iso: string, language: Language): string {
  return new Intl.DateTimeFormat(locales[language], { hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
}

export function formatShortDate(iso: string, language: Language): string {
  return new Intl.DateTimeFormat(locales[language], { day: 'numeric', month: 'short' }).format(new Date(iso))
}

export function formatPercent(value: number, language: Language): string {
  return new Intl.NumberFormat(locales[language], { style: 'percent', maximumFractionDigits: 0 }).format(value)
}

/** In-app link to an item's detail page; `from` keeps the edition for the back link. */
export function itemPath(itemId: string, language: Language, fromEdition?: string): string {
  const params = new URLSearchParams({ lang: language })
  if (fromEdition) params.set('from', fromEdition)
  return `/items/${encodeURIComponent(itemId)}?${params}`
}
