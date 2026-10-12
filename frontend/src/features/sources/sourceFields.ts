import type { MessageKey } from '../../lib/i18n'
import type { SourceEntry, SourceValues } from '../../lib/api'

/** How each editable field is shown. Limits mirror the API, which checks them again. */
export type FieldMeta =
  | { input: 'text'; mono?: boolean; required?: boolean }
  | { input: 'url'; required?: boolean }
  | { input: 'number'; min: number; max: number }
  | { input: 'select'; options: string[] }
  | { input: 'list' }

export const fieldMeta: Record<string, FieldMeta> = {
  name: { input: 'text', required: true },
  url: { input: 'url', required: true },
  repository: { input: 'text', mono: true, required: true },
  username: { input: 'text', mono: true, required: true },
  subreddit: { input: 'text', mono: true, required: true },
  channel: { input: 'text', mono: true, required: true },
  sort: { input: 'select', options: ['hot', 'new', 'top', 'rising'] },
  fetch_limit: { input: 'number', min: 1, max: 100 },
  min_score: { input: 'number', min: 0, max: 100000 },
  fetch_top_stories: { input: 'number', min: 1, max: 200 },
  fetch_comments: { input: 'number', min: 0, max: 50 },
  period: { input: 'select', options: ['past_24_hours', 'past_28_days'] },
  languages: { input: 'list' },
  keywords: { input: 'list' },
  min_stars: { input: 'number', min: 0, max: 1000000 },
  max_items: { input: 'number', min: 1, max: 100 },
  query: { input: 'text', required: true },
  max_records: { input: 'number', min: 1, max: 250 },
  max_results: { input: 'number', min: 1, max: 100 },
  language: { input: 'text', mono: true },
  country: { input: 'text', mono: true },
}

/** Fields of each kind that can be added from the web app, in display order. */
export const addableKinds = ['rss', 'github_repo', 'github_user', 'reddit_subreddit', 'reddit_user', 'telegram_channel'] as const

export const fieldsWithHint = new Set(['name', 'url', 'repository', 'subreddit', 'channel', 'min_score', 'languages', 'keywords', 'language', 'country'])

export const fieldLabelKey = (name: string) => `sourceField.${name}` as MessageKey
export const fieldHintKey = (name: string) => `sourceField.${name}.hint` as MessageKey
export const optionKey = (value: string) => `sourceOption.${value}` as MessageKey
export const kindKey = (kind: string) => `sources.kind.${kind}` as MessageKey

export type FormValues = Record<string, string>

/** API values -> strings for the inputs (lists joined with commas). */
export function toForm(values: SourceValues): FormValues {
  return Object.fromEntries(
    Object.entries(values).map(([name, value]) => [name, Array.isArray(value) ? value.join(', ') : value === null || value === undefined ? '' : String(value)]),
  )
}

/** Inputs -> API values, or the first problem of each field. */
export function fromForm(
  fields: string[],
  form: FormValues,
): { values: SourceValues; errors: Record<string, { key: MessageKey; params?: Record<string, number> }> } {
  const values: SourceValues = {}
  const errors: Record<string, { key: MessageKey; params?: Record<string, number> }> = {}
  for (const name of fields) {
    const meta = fieldMeta[name] ?? { input: 'text' }
    const raw = (form[name] ?? '').trim()
    if (meta.input === 'number') {
      const value = Number(raw)
      if (raw === '' || !Number.isInteger(value) || value < meta.min || value > meta.max) {
        errors[name] = { key: 'sources.integer', params: { min: meta.min, max: meta.max } }
      } else {
        values[name] = value
      }
    } else if (meta.input === 'list') {
      values[name] = raw
        .split(',')
        .map((entry) => entry.trim())
        .filter(Boolean)
    } else if ((meta.input === 'text' || meta.input === 'url') && meta.required && !raw) {
      errors[name] = { key: 'sources.required' }
    } else {
      values[name] = raw
    }
  }
  return { values, errors }
}

/** Only what differs from the saved source: unchanged fields stay as written in config.json. */
export function changedValues(entry: SourceEntry, values: SourceValues): SourceValues {
  return Object.fromEntries(Object.entries(values).filter(([name, value]) => JSON.stringify(entry.values[name] ?? null) !== JSON.stringify(value)))
}
