import { CircleCheck, CircleX, Megaphone, TriangleAlert, VolumeX, type LucideIcon } from 'lucide-react'
import type { HealthStatus, SourceHealth } from '../../lib/api'
import type { Language, MessageKey } from '../../lib/i18n'
import { translate } from '../../lib/i18n'
import { sourceName } from '../../lib/format'

// Status = icon + label + colour, never colour alone.
export const healthStyles: Record<HealthStatus, { icon: LucideIcon; tone: string }> = {
  dead: { icon: CircleX, tone: 'bg-rumor/10 text-rumor ring-rumor/20' },
  failing: { icon: TriangleAlert, tone: 'bg-failing/10 text-failing ring-failing/20' },
  silent: { icon: VolumeX, tone: 'bg-muted/10 text-muted ring-muted/20' },
  noisy: { icon: Megaphone, tone: 'bg-unverified/10 text-unverified ring-unverified/20' },
  healthy: { icon: CircleCheck, tone: 'bg-confirmed/10 text-confirmed ring-confirmed/20' },
}

/** `rss/LWN.net` -> `LWN.net`, `github/@karpathy` -> `@karpathy`, `hackernews` -> `Hacker News`. */
export function sourceLabel(health: Pick<SourceHealth, 'source' | 'type'>): string {
  const prefix = `${health.type}/`
  return health.source.startsWith(prefix) ? health.source.slice(prefix.length) : sourceName(health.source)
}

/** Localized reason, rebuilt from the numbers (the API's reasons are English). */
export function healthReason(health: SourceHealth, language: Language): string {
  const t = (key: MessageKey, params?: Record<string, number>) => translate(language, key, params)
  switch (health.status) {
    case 'dead':
      return t('reason.dead', { count: health.consecutive_failures })
    case 'failing':
      return t('reason.failing', { failures: health.failures, runs: health.runs })
    case 'silent':
      return t('reason.silent', { runs: health.runs })
    case 'noisy':
      return t('reason.noisy', { selected: health.selected, items: health.items })
    case 'healthy':
      return health.items === 0 ? t('reason.empty') : ''
  }
}
