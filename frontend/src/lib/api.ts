import { z } from 'zod'

// Mirrors src/web_api.py. Parsing at the boundary keeps the UI honest about the data.

export const reliabilityLabels = ['confirmed', 'reliable', 'unverified', 'rumor'] as const
export const sourceTiers = ['official', 'reputable', 'community', 'unknown'] as const

const reliabilitySchema = z.object({
  label: z.enum(reliabilityLabels),
  source_tier: z.enum(sourceTiers),
  source_domain: z.string(),
  claim_status: z.string().nullable(),
  corroborated_by: z.array(z.string()),
  reasons: z.array(z.string()),
})

const itemSchema = z.object({
  id: z.string(),
  title: z.string(),
  url: z.string(),
  score: z.number().nullable(),
  importance: z.enum(['critical', 'high', 'medium', 'low']).nullable(),
  categories: z.array(z.string()),
  tags: z.array(z.string()),
  summary: z.string(),
  sections: z.array(z.object({ id: z.string(), title: z.string(), content: z.string() })),
  reliability: reliabilitySchema.nullable(),
  source_type: z.string(),
  author: z.string().nullable(),
  published_at: z.string(),
  discussion_url: z.string().nullable().optional(),
  translated: z.boolean(),
  /** Not analyzed: the AI quota ran out. Original headline, no AI content. */
  ai_skipped: z.boolean().default(false),
})

export const aiLimits = ['provider_quota', 'token_budget'] as const

const runSchema = z.object({
  id: z.string(),
  started_at: z.string(),
  finished_at: z.string().nullable(),
  fetched_count: z.number(),
  selected_count: z.number(),
  /** Why the AI stopped during the run: daily quota, or the run's token budget. */
  ai_limit: z.enum(aiLimits).nullable().default(null),
  tokens_used: z.number().default(0),
  ai_skipped_count: z.number().default(0),
})

export const editionListSchema = z.object({ editions: z.array(runSchema) })

export const healthStatuses = ['dead', 'failing', 'silent', 'noisy', 'healthy'] as const

const sourceHealthSchema = z.object({
  source: z.string(),
  type: z.string(),
  status: z.enum(healthStatuses),
  runs: z.number(),
  failures: z.number(),
  consecutive_failures: z.number(),
  empty_runs: z.number(),
  items: z.number(),
  selected: z.number(),
  selection_rate: z.number(),
  last_success_at: z.string().nullable(),
  last_error: z.string().nullable(),
})

export const sourceReportSchema = z.object({
  days: z.number(),
  sources: z.array(sourceHealthSchema),
  configured_without_history: z.array(z.string()),
  runs: z.array(runSchema),
})

export const editionSchema = runSchema.extend({
  language: z.string(),
  available_languages: z.array(z.string()),
  sections: z.array(
    z.object({ profile: z.string(), name: z.string(), items: z.array(itemSchema) }),
  ),
  /** Items published without analysis because the AI quota ran out. */
  unanalyzed: z.array(itemSchema).default([]),
})

export const claimStatuses = ['confirmed', 'reported', 'unverified', 'rumor'] as const

export const itemDetailSchema = itemSchema.extend({
  language: z.string(),
  available_languages: z.array(z.string()),
  profile: z.string(),
  profile_name: z.string(),
  claim: z.object({ status: z.enum(claimStatuses), evidence: z.string() }).nullable(),
  editions: z.array(runSchema),
})

export type ItemDetail = z.infer<typeof itemDetailSchema>
export type ClaimStatus = (typeof claimStatuses)[number]
export type Run = z.infer<typeof runSchema>
export type AiLimit = (typeof aiLimits)[number]
export type Edition = z.infer<typeof editionSchema>
export type SourceReport = z.infer<typeof sourceReportSchema>
export type SourceHealth = z.infer<typeof sourceHealthSchema>
export type HealthStatus = (typeof healthStatuses)[number]
export type EditionItem = z.infer<typeof itemSchema>
export type Reliability = z.infer<typeof reliabilitySchema>
export type ReliabilityLabel = (typeof reliabilityLabels)[number]
export type SourceTier = (typeof sourceTiers)[number]

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** Field-level validation messages from the API (422/409). */
    readonly fields: Record<string, string> = {},
  ) {
    super(message)
  }
}

async function request<T>(path: string, schema: z.ZodType<T>, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(body?.error ?? `API responded ${response.status}`, response.status, body?.fields ?? {})
  }
  return schema.parse(await response.json())
}

function getJson<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
  return request(path, schema, { signal })
}

export function fetchEdition(id: string, language: string, signal?: AbortSignal): Promise<Edition> {
  return getJson(`/api/editions/${encodeURIComponent(id)}?lang=${encodeURIComponent(language)}`, editionSchema, signal)
}

export async function fetchEditions(signal?: AbortSignal): Promise<Run[]> {
  return (await getJson('/api/editions', editionListSchema, signal)).editions
}

export function fetchSourceReport(days: number, signal?: AbortSignal): Promise<SourceReport> {
  return getJson(`/api/sources?days=${days}`, sourceReportSchema, signal)
}

export function fetchItem(id: string, language: string, signal?: AbortSignal): Promise<ItemDetail> {
  return getJson(`/api/items/${encodeURIComponent(id)}?lang=${encodeURIComponent(language)}`, itemDetailSchema, signal)
}

// Subscriber preferences (local-only routes, see src/subscribers_api.py) -------------

export const frequencies = ['daily', 'weekly'] as const
export const importanceLevels = ['low', 'medium', 'high', 'critical'] as const

export const preferencesSchema = z.object({
  language: z.string(),
  categories: z.array(z.string()),
  sources: z.array(z.string()),
  frequency: z.enum(frequencies),
  min_importance: z.enum(importanceLevels).nullable(),
  include_unconfirmed: z.boolean(),
  max_items: z.number().int().nullable(),
})

const subscriberSchema = z.object({
  id: z.string(),
  email: z.string(),
  plan: z.enum(['free', 'premium']),
  preferences: preferencesSchema,
  created_at: z.string(),
})

const optionsSchema = z.object({
  languages: z.array(z.object({ code: z.string(), name: z.string() })),
  categories: z.array(z.string()),
  frequencies: z.array(z.enum(frequencies)),
  importance_levels: z.array(z.enum(importanceLevels)),
  sources: z.array(z.object({ value: z.string(), type: z.string(), kind: z.enum(['type', 'source']) })),
  plans: z.array(
    z.object({
      id: z.enum(['free', 'premium']),
      max_categories: z.number().nullable(),
      max_sources: z.number().nullable(),
      max_items: z.number().nullable(),
    }),
  ),
})

export type Preferences = z.infer<typeof preferencesSchema>
export type Subscriber = z.infer<typeof subscriberSchema>
export type PreferenceOptions = z.infer<typeof optionsSchema>

export function fetchPreferenceOptions(signal?: AbortSignal): Promise<PreferenceOptions> {
  return getJson('/api/preferences/options', optionsSchema, signal)
}

export async function fetchSubscribers(signal?: AbortSignal): Promise<Subscriber[]> {
  return (await getJson('/api/subscribers', z.object({ subscribers: z.array(subscriberSchema) }), signal)).subscribers
}

export function createSubscriber(email: string): Promise<Subscriber> {
  return request('/api/subscribers', subscriberSchema, { method: 'POST', body: JSON.stringify({ email }) })
}

export function updatePreferences(id: string, preferences: Preferences): Promise<Subscriber> {
  return request(`/api/subscribers/${encodeURIComponent(id)}`, subscriberSchema, {
    method: 'PUT',
    body: JSON.stringify({ preferences }),
  })
}

export function deleteSubscriber(id: string): Promise<{ deleted: string }> {
  return request(`/api/subscribers/${encodeURIComponent(id)}`, z.object({ deleted: z.string() }), {
    method: 'DELETE',
  })
}

// Quality evaluation (local-only routes, see src/evaluation/) ---------------------

export const annotationSchema = z.object({
  item_id: z.string(),
  relevant: z.boolean(),
  importance: z.enum(importanceLevels),
  categories: z.array(z.string()),
  claim_status: z.enum(claimStatuses),
  notes: z.string(),
  annotated_at: z.string(),
})

const evalItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  url: z.string(),
  source_type: z.string(),
  source: z.string(),
  author: z.string().nullable(),
  published_at: z.string(),
  excerpt: z.string(),
  discussion_url: z.string().nullable().optional(),
  annotation: annotationSchema.nullable(),
})

const rate = z.number().nullable()
const matrix = z.record(z.string(), z.record(z.string(), z.number()))

const comparisonSchema = z.object({
  item_id: z.string(),
  title: z.string(),
  issues: z.array(z.string()),
  human: z.object({
    relevant: z.boolean(),
    importance: z.string(),
    categories: z.array(z.string()),
    claim_status: z.string(),
    reliability: z.string().nullable(),
    notes: z.string(),
  }),
  ai: z.object({
    score: z.number().nullable(),
    selected: z.boolean(),
    importance: z.string().nullable(),
    categories: z.array(z.string()),
    claim_status: z.string().nullable(),
    reliability: z.string().nullable(),
  }),
})

export const reportSchema = z.object({
  annotated: z.number(),
  compared: z.number(),
  missing: z.array(z.string()),
  small_sample: z.boolean(),
  selection: z.object({
    true_positive: z.number(),
    false_positive: z.number(),
    false_negative: z.number(),
    true_negative: z.number(),
    precision: rate,
    recall: rate,
    f1: rate,
    accuracy: rate,
  }),
  importance: z.object({ exact: rate, within_one: rate, mean_band_error: rate, confusion: matrix }),
  categories: z.object({ precision: rate, recall: rate, f1: rate, exact_match: rate }),
  claim: z.object({ accuracy: rate, overconfident: z.number(), confusion: matrix }),
  reliability: z.object({ agreement: rate, false_reliable: z.number(), false_reliable_items: z.array(z.string()) }),
  items: z.array(comparisonSchema),
})

export type Annotation = z.infer<typeof annotationSchema>
export type AnnotationInput = Omit<Annotation, 'item_id' | 'annotated_at'>
export type EvalItem = z.infer<typeof evalItemSchema>
export type QualityReport = z.infer<typeof reportSchema>
export type Comparison = z.infer<typeof comparisonSchema>

export function fetchEvalItems(signal?: AbortSignal) {
  return getJson('/api/eval/items', z.object({ items: z.array(evalItemSchema), annotated: z.number() }), signal)
}

export function fetchQualityReport(signal?: AbortSignal): Promise<QualityReport> {
  return getJson('/api/eval/report', reportSchema, signal)
}

export function saveAnnotation(itemId: string, annotation: AnnotationInput): Promise<Annotation> {
  return request(`/api/eval/annotations/${encodeURIComponent(itemId)}`, annotationSchema, {
    method: 'PUT',
    body: JSON.stringify(annotation),
  })
}

export function deleteAnnotation(itemId: string): Promise<{ deleted: string }> {
  return request(`/api/eval/annotations/${encodeURIComponent(itemId)}`, z.object({ deleted: z.string() }), {
    method: 'DELETE',
  })
}
