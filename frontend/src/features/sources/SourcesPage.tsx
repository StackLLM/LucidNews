import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { useState, type ReactNode } from 'react'
import { ApiErrorCard, PageHeader, PageSkeleton, Segmented } from '../../design/PageState'
import { ApiError, fetchSourceConfig, fetchSourceReport, healthStatuses, type HealthStatus, type SourceHealth, type SourceReport } from '../../lib/api'
import { formatItemTime, formatPercent, sourceName } from '../../lib/format'
import { healthKey, useLanguage } from '../../lib/i18n'
import { listStagger, riseIn, useMotionPreference } from '../../lib/motion'
import { sourceLabel } from './healthStyles'
import { RunVolumeChart } from './RunVolumeChart'
import { HealthBadge, QualityScore, SourceDetail } from './SourceBits'
import { SourceManager } from './SourceManager'

const PERIODS = [7, 14, 30] as const

export function SourcesPage() {
  const { t } = useLanguage()
  const [days, setDays] = useState<number>(14)
  const query = useQuery({
    queryKey: ['sources', days],
    queryFn: ({ signal }) => fetchSourceReport(days, signal),
    placeholderData: keepPreviousData,
  })

  const period = (
    <Segmented
      id="period"
      label={t('sources.period')}
      value={days}
      onChange={setDays}
      options={PERIODS.map((value) => ({ value, label: t('sources.days', { days: value }) }))}
    />
  )

  if (query.isPending) return <PageSkeleton />
  if (query.isError) return <ApiErrorCard error={query.error} onRetry={() => query.refetch()} />
  return <SourcesView report={query.data} period={period} />
}

function SourcesView({ report, period }: { report: SourceReport; period: ReactNode }) {
  const { t } = useLanguage()
  const { enabled } = useMotionPreference()
  // Local API only: elsewhere the page stays the read-only health view.
  const config = useQuery({
    queryKey: ['source-config'],
    queryFn: ({ signal }) => fetchSourceConfig(signal),
    retry: (failures, error) => !(error instanceof ApiError && error.status === 403) && failures < 2,
  })
  const managed = config.isSuccess
  const count = (...statuses: HealthStatus[]) => report.sources.filter((s) => statuses.includes(s.status)).length

  const tiles = [
    { label: t('sources.tracked'), value: report.sources.length + report.configured_without_history.length },
    { label: t('sources.healthy'), value: count('healthy'), tone: 'text-confirmed' },
    { label: t('sources.watch'), value: count('silent', 'noisy'), tone: 'text-unverified' },
    { label: t('sources.broken'), value: count('dead', 'failing'), tone: 'text-rumor' },
  ]

  return (
    <motion.div variants={listStagger} initial={enabled ? 'hidden' : false} animate="visible" className="space-y-6">
      <PageHeader title={t('sources.title')} subtitle={t('sources.subtitle')} actions={period} />

      <motion.dl variants={riseIn} className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {tiles.map((tile) => (
          <div key={tile.label} className="glass rounded-card px-5 py-4">
            <dt className="text-[13px] font-medium text-muted">{tile.label}</dt>
            <dd className={`mt-1 text-[32px] leading-none font-bold ${tile.value > 0 && tile.tone ? tile.tone : 'text-ink'}`}>
              {tile.value}
            </dd>
          </div>
        ))}
      </motion.dl>

      {!managed && report.configured_without_history.length > 0 && (
        <motion.p variants={riseIn} className="rounded-control bg-white/70 px-4 py-3 text-[13.5px] text-muted">
          {t('sources.neverSeen', { list: report.configured_without_history.join(', ') })}
        </motion.p>
      )}

      <motion.div variants={riseIn}>
        <RunVolumeChart runs={report.runs} />
      </motion.div>

      <motion.div variants={riseIn}>
        {managed ? (
          <SourceManager config={config.data} health={report.sources} onReload={() => config.refetch()} />
        ) : config.isPending ? (
          <div className="h-64 animate-shimmer rounded-card bg-white/70 shadow-card" />
        ) : (
          <>
            {!(config.error instanceof ApiError && config.error.status === 403) && (
              <div className="mb-6">
                <ApiErrorCard error={config.error!} onRetry={() => config.refetch()} />
              </div>
            )}
            <SourceTable sources={report.sources} qualityDays={report.quality_days} />
          </>
        )}
        {managed && <p className="mt-4 text-[12.5px] leading-relaxed text-muted">{t('sources.qualityHint', { days: report.quality_days })}</p>}
      </motion.div>
    </motion.div>
  )
}

function SourceTable({ sources, qualityDays }: { sources: SourceHealth[]; qualityDays: number }) {
  const { language, t } = useLanguage()
  const [filter, setFilter] = useState<HealthStatus | 'all'>('all')
  const visible = filter === 'all' ? sources : sources.filter((source) => source.status === filter)
  const options = [
    { value: 'all' as const, label: `${t('sources.filterAll')} · ${sources.length}` },
    ...healthStatuses
      .map((status) => ({ status, total: sources.filter((source) => source.status === status).length }))
      .filter(({ total }) => total > 0)
      .map(({ status, total }) => ({ value: status, label: `${t(healthKey(status))} · ${total}` })),
  ]

  return (
    <section aria-labelledby="sources-list" className="rounded-card bg-surface p-5 shadow-card sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 id="sources-list" className="text-[17px] font-bold">
          {t('sources.list')}
        </h2>
        <Segmented id="status-filter" label={t('sources.col.status')} value={filter} onChange={setFilter} options={options} />
      </div>

      {visible.length === 0 ? (
        <p className="mt-6 text-[14px] text-muted">{t('sources.noneMatch')}</p>
      ) : (
        <>
          {/* Desktop: table. Phone: one card per source. */}
          {/* Between md and xl the 9 columns can be wider than the card: scroll inside it. */}
          <div className="mt-5 hidden overflow-x-auto md:block">
            <table className="w-full text-[14px]">
              <thead>
                <tr className="border-b border-line text-left text-[12px] text-faint">
                  <th className="py-3 pr-4 font-semibold">{t('sources.col.source')}</th>
                  <th className="py-3 pr-4 font-semibold">{t('sources.col.status')}</th>
                  <th className="py-3 pr-4 text-right font-semibold">{t('sources.col.runs')}</th>
                  <th className="py-3 pr-4 text-right font-semibold">{t('sources.col.failures')}</th>
                  <th className="py-3 pr-4 text-right font-semibold">{t('sources.col.perRun')}</th>
                  <th className="py-3 pr-4 text-right font-semibold">{t('sources.col.selected')}</th>
                  <th className="py-3 pr-4 text-right font-semibold">{t('sources.col.quality')}</th>
                  <th className="py-3 pr-4 font-semibold">{t('sources.col.lastSuccess')}</th>
                  <th className="py-3 font-semibold">{t('sources.col.detail')}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((source) => (
                  <tr key={source.source} className="border-b border-line/70 transition-colors duration-150 last:border-0 hover:bg-canvas/60">
                    <td className="max-w-56 py-3.5 pr-4">
                      <p className="truncate font-semibold" title={source.source}>
                        {sourceLabel(source)}
                      </p>
                      <p className="text-[12px] text-faint">{sourceName(source.type)}</p>
                    </td>
                    <td className="py-3.5 pr-4">
                      <HealthBadge status={source.status} />
                    </td>
                    <td className="py-3.5 pr-4 text-right tabular-nums">{source.runs}</td>
                    <td className="py-3.5 pr-4 text-right tabular-nums">{source.failures}</td>
                    <td className="py-3.5 pr-4 text-right tabular-nums">{(source.items / Math.max(source.runs, 1)).toFixed(1)}</td>
                    <td className="py-3.5 pr-4 text-right tabular-nums">
                      {source.selected}
                      {source.items > 0 && (
                        <span className="ml-1 text-faint">({formatPercent(source.selection_rate, language)})</span>
                      )}
                    </td>
                    <td className="py-3.5 pr-4 text-right">
                      <QualityScore source={source} />
                    </td>
                    <td className="py-3.5 pr-4 whitespace-nowrap text-muted">
                      {source.last_success_at ? formatItemTime(source.last_success_at, language) : t('sources.never')}
                    </td>
                    <td className="max-w-64 py-3.5 text-[13px] text-muted">
                      <SourceDetail source={source} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="mt-5 space-y-3 md:hidden">
            {visible.map((source) => (
              <li key={source.source} className="rounded-2xl bg-canvas/70 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{sourceLabel(source)}</p>
                    <p className="text-[12px] text-faint">{sourceName(source.type)}</p>
                  </div>
                  <HealthBadge status={source.status} />
                </div>
                <p className="mt-2 text-[13px] text-muted tabular-nums">
                  {t('sources.col.runs')} {source.runs} · {t('sources.col.failures')} {source.failures} ·{' '}
                  {t('sources.col.selected')} {source.selected}
                  {source.quality && (
                    <>
                      {' '}· {t('sources.col.quality')} <QualityScore source={source} />
                    </>
                  )}
                </p>
                <p className="mt-1 text-[13px] text-muted">
                  <SourceDetail source={source} />
                </p>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-[12.5px] leading-relaxed text-muted">{t('sources.qualityHint', { days: qualityDays })}</p>
        </>
      )}
    </section>
  )
}
