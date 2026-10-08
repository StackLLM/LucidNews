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
})

const runSchema = z.object({
  id: z.string(),
  started_at: z.string(),
  finished_at: z.string().nullable(),
  fetched_count: z.number(),
  selected_count: z.number(),
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
  ) {
    super(message)
  }
}

async function getJson<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, headers: { Accept: 'application/json' } })
  if (!response.ok) {
    throw new ApiError(`API responded ${response.status}`, response.status)
  }
  return schema.parse(await response.json())
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
