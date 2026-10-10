import type { HealthStatus, SourceHealth } from '../../lib/api'
import { formatPercent } from '../../lib/format'
import { healthKey, useLanguage } from '../../lib/i18n'
import { healthReason, healthStyles } from './healthStyles'

/** Pieces of the health view shared by the read-only table and the source manager. */
export function QualityScore({ source }: { source: SourceHealth }) {
  const { language, t } = useLanguage()
  const quality = source.quality
  if (!quality) return <span className="text-faint">–</span>
  const value = Math.round(quality.score * 100)
  return (
    <span
      className="inline-flex items-center gap-2 tabular-nums"
      title={t('sources.qualityTitle', {
        mean: quality.mean_score.toFixed(1),
        trusted: formatPercent(quality.trusted_share, language),
        count: quality.items,
      })}
    >
      <span aria-hidden className="hidden h-1.5 w-10 overflow-hidden rounded-full bg-accent-soft lg:block">
        <span className="block h-full rounded-full bg-accent" style={{ width: `${value}%` }} />
      </span>
      <span className="font-semibold">{value}</span>
    </span>
  )
}

export function SourceDetail({ source }: { source: SourceHealth }) {
  const { language } = useLanguage()
  const reason = healthReason(source, language)
  const showError = source.last_error && (source.status === 'dead' || source.status === 'failing')
  return (
    <>
      {reason}
      {showError && (
        <span className="mt-0.5 block truncate font-mono text-[12px] text-faint" title={source.last_error ?? ''}>
          {source.last_error}
        </span>
      )}
    </>
  )
}

export function HealthBadge({ status }: { status: HealthStatus }) {
  const { t } = useLanguage()
  const { icon: Icon, tone } = healthStyles[status]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12.5px] font-semibold whitespace-nowrap ring-1 ring-inset ${tone}`}>
      <Icon size={14} strokeWidth={2.25} aria-hidden />
      {t(healthKey(status))}
    </span>
  )
}
