import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { m } from 'motion/react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { ApiErrorCard, PageSkeleton, Segmented } from '../../design/PageState'
import { fetchQualityOverview, healthStatuses, reliabilityLabels, type QualityOverview } from '../../lib/api'
import { formatItemTime, formatPercent } from '../../lib/format'
import { categoryLabel, labelKey, translatePlural, useLanguage, type MessageKey } from '../../lib/i18n'
import { listStagger, riseIn, useMotionPreference } from '../../lib/motion'
import { keyLabel } from '../sources/DomainsView'
import { HealthBadge } from '../sources/SourceBits'

const PERIODS = [7, 14, 30] as const
const LABEL_COLORS: Record<(typeof reliabilityLabels)[number], string> = {
  confirmed: 'bg-confirmed',
  reliable: 'bg-reliable',
  unverified: 'bg-unverified',
  rumor: 'bg-rumor',
}

/** Indicators of the watch over a period. Each card names where its numbers come from. */
export function OverviewView() {
  const { t } = useLanguage()
  const [days, setDays] = useState<number>(14)
  const query = useQuery({
    queryKey: ['quality-overview', days],
    queryFn: ({ signal }) => fetchQualityOverview(days, signal),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Segmented
          id="overview-period"
          label={t('overview.period')}
          value={days}
          onChange={setDays}
          options={PERIODS.map((value) => ({ value, label: t('sources.days', { days: value }) }))}
        />
      </div>
      {query.isPending ? (
        <PageSkeleton />
      ) : query.isError ? (
        <ApiErrorCard error={query.error} onRetry={() => query.refetch()} />
      ) : (
        <Overview data={query.data} />
      )}
    </div>
  )
}

function Overview({ data }: { data: QualityOverview }) {
  const { language, t } = useLanguage()
  const { enabled } = useMotionPreference()
  const labels = data.reliability.labels
  const labelled = reliabilityLabels.reduce((sum, label) => sum + labels[label], 0)
  const trusted = labelled ? (labels.confirmed + labels.reliable) / labelled : null
  const noData = t('overview.noData')

  const tiles = [
    {
      label: t('overview.coverage.tile'),
      value: data.coverage.watched ? `${data.coverage.gaps.length}/${data.coverage.watched}` : noData,
      tone: data.coverage.gaps.length ? 'text-rumor' : 'text-confirmed',
    },
    { label: t('overview.diversity.tile'), value: `${data.diversity.active_sources}/${data.diversity.configured_sources}` },
    {
      label: t('overview.freshness.tile'),
      value: data.freshness.median_hours === null ? noData : t('overview.freshness.hours', { hours: formatNumber(data.freshness.median_hours, language) }),
    },
    { label: t('overview.reliability.tile'), value: trusted === null ? noData : formatPercent(trusted, language) },
  ]

  return (
    <m.div variants={listStagger} initial={enabled ? 'hidden' : false} animate="visible" className="space-y-6">
      <m.dl variants={riseIn} className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {tiles.map((tile) => (
          <div key={tile.label} className="glass rounded-card px-5 py-4">
            <dt className="text-[13px] font-medium text-muted">{tile.label}</dt>
            <dd
              className={`mt-1 text-[28px] leading-none font-bold sm:text-[32px] ${tile.value === noData ? 'text-[18px]! text-faint' : (tile.tone ?? 'text-ink')}`}
            >
              {tile.value}
            </dd>
          </div>
        ))}
      </m.dl>

      <m.div variants={riseIn} className="grid gap-6 lg:grid-cols-2">
        <Card title={t('overview.coverage')} source={[t('overview.source.items')]} days={data.days}>
          {data.coverage.gaps.length === 0 ? (
            <p className="text-[14px] text-confirmed">{t('overview.coverage.none')}</p>
          ) : (
            <>
              <p className="text-[14px]">{t('overview.coverage.value', { gaps: data.coverage.gaps.length, watched: data.coverage.watched })}</p>
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {data.coverage.gaps.map((category) => (
                  <li key={category} className="rounded-full bg-rumor/10 px-2.5 py-1 text-[12.5px] font-semibold text-rumor">
                    {categoryLabel(language, category)}
                  </li>
                ))}
              </ul>
            </>
          )}
          <MoreLink to={`/sources?tab=domains&lang=${language}`}>{t('overview.coverage.link')}</MoreLink>
        </Card>

        <Card title={t('overview.diversity')} source={[t('overview.source.sources'), t('overview.source.runs')]} days={data.days}>
          <ul className="space-y-1.5 text-[14px]">
            <li>
              {t('overview.diversity.active', {
                active: data.diversity.active_sources,
                configured: data.diversity.configured_sources,
              })}
            </li>
            <li>{t('overview.diversity.publishing', { count: data.diversity.publishing_sources })}</li>
            {data.diversity.top_collected && (
              <li>
                {t('overview.diversity.topCollected', {
                  source: keyLabel(data.diversity.top_collected.source),
                  share: formatPercent(data.diversity.top_collected.share, language),
                })}
              </li>
            )}
            {data.diversity.top_published && (
              <li>
                {t('overview.diversity.topPublished', {
                  source: keyLabel(data.diversity.top_published.source),
                  share: formatPercent(data.diversity.top_published.share, language),
                })}
              </li>
            )}
          </ul>
        </Card>

        <Card title={t('overview.health')} source={[t('overview.source.sources')]} days={data.days}>
          <ul className="flex flex-wrap gap-2">
            {healthStatuses.map((status) => (
              <li key={status} className="flex items-center gap-1.5">
                <HealthBadge status={status} />
                <span className="text-[14px] font-semibold tabular-nums">{data.health.by_status[status] ?? 0}</span>
              </li>
            ))}
          </ul>
          {data.health.never_collected > 0 && (
            <p className="mt-3 text-[13.5px] text-muted">{t('overview.health.never', { count: data.health.never_collected })}</p>
          )}
          <h4 className="mt-4 text-[13px] font-semibold text-ink/80">{t('overview.health.errors')}</h4>
          {data.health.recent_errors.length === 0 ? (
            <p className="mt-1 text-[13.5px] text-muted">{t('overview.health.noError')}</p>
          ) : (
            <ul className="mt-1.5 space-y-1.5">
              {data.health.recent_errors.map((error) => (
                <li key={`${error.source}-${error.at}`} className="text-[13px]">
                  <span className="font-semibold">{keyLabel(error.source)}</span>
                  <span className="ml-1.5 text-faint">{formatItemTime(error.at, language)}</span>
                  {error.error && (
                    <span className="block truncate font-mono text-[12px] text-muted" title={error.error}>
                      {error.error}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title={t('overview.freshness')} source={[t('overview.source.runs'), t('overview.source.items')]} days={data.days}>
          {data.freshness.median_hours === null ? (
            <p className="text-[14px] text-muted">{t('overview.reliability.none')}</p>
          ) : (
            <p className="text-[14px] leading-relaxed">
              {t('overview.freshness.detail', {
                median: formatNumber(data.freshness.median_hours, language),
                p90: formatNumber(data.freshness.p90_hours ?? 0, language),
                share: formatPercent(data.freshness.within_24h ?? 0, language),
              })}
            </p>
          )}
        </Card>

        <Card title={t('overview.selection')} source={[t('overview.source.runs')]} days={data.days}>
          <SelectionFunnel data={data} />
        </Card>

        <Card title={t('overview.filtering')} source={[t('overview.source.annotations')]} days={data.days}>
          <Filtering data={data} />
        </Card>

        <Card title={t('overview.reliability')} source={[t('overview.source.runs'), t('overview.source.items')]} days={data.days}>
          {labelled === 0 && data.reliability.unanalyzed === 0 ? (
            <p className="text-[14px] text-muted">{t('overview.reliability.none')}</p>
          ) : (
            <>
              {labelled > 0 && (
                <div className="flex h-3 overflow-hidden rounded-full bg-canvas" aria-hidden>
                  {reliabilityLabels.map((label) =>
                    labels[label] ? <span key={label} className={LABEL_COLORS[label]} style={{ width: `${(labels[label] / labelled) * 100}%` }} /> : null,
                  )}
                </div>
              )}
              <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[13.5px]">
                {reliabilityLabels.map((label) => (
                  <li key={label} className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-[3px] ${LABEL_COLORS[label]}`} aria-hidden />
                    {t(labelKey(label))}
                    <span className="ml-auto font-semibold tabular-nums">{labels[label]}</span>
                  </li>
                ))}
              </ul>
              {data.reliability.unanalyzed > 0 && (
                <p className="mt-3 text-[13px] text-muted">{t('overview.reliability.unanalyzed', { count: data.reliability.unanalyzed })}</p>
              )}
            </>
          )}
        </Card>
      </m.div>
    </m.div>
  )
}

function SelectionFunnel({ data }: { data: QualityOverview }) {
  const { language, t } = useLanguage()
  const { enabled } = useMotionPreference()
  const selection = data.selection
  const withData = selection.per_run.filter((run) => run.above_threshold !== null)
  if (withData.length === 0) {
    return <p className="text-[14px] text-muted">{t('overview.selection.none')}</p>
  }
  const published = withData.reduce((sum, run) => sum + run.selected, 0)
  const steps: { key: MessageKey; value: number }[] = [
    { key: 'overview.selection.fetched', value: selection.fetched ?? 0 },
    { key: 'overview.selection.urlMerged', value: selection.url_merged ?? 0 },
    { key: 'overview.selection.aboveThreshold', value: selection.above_threshold ?? 0 },
    { key: 'overview.selection.topicMerged', value: selection.topic_merged ?? 0 },
    { key: 'overview.selection.selected', value: published },
  ]
  const points = steps.map((step) => ({ label: t(step.key), value: step.value }))
  const merges = new Set([t('overview.selection.urlMerged'), t('overview.selection.topicMerged')])

  return (
    <>
      <p className="text-[13px] text-muted">{t('overview.selection.hint')}</p>
      <div className="mt-3 h-52" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={points} layout="vertical" margin={{ top: 0, right: 36, bottom: 0, left: 8 }} barCategoryGap="22%">
            <CartesianGrid horizontal={false} stroke="var(--color-line)" />
            <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: 'var(--color-faint)', fontSize: 11 }} />
            <YAxis type="category" dataKey="label" width={156} tickLine={false} axisLine={false} tick={{ fill: 'var(--color-muted)', fontSize: 12 }} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive={enabled}>
              {points.map((point) => (
                <Cell key={point.label} fill={merges.has(point.label) ? 'var(--color-series-collected)' : 'var(--color-series-selected)'} />
              ))}
              <LabelList dataKey="value" position="right" fill="var(--color-ink)" fontSize={12} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {/* Same numbers as text, for screen readers and copy. */}
      <dl className="sr-only">
        {points.map((point) => (
          <div key={point.label}>
            <dt>{point.label}</dt>
            <dd>{point.value.toLocaleString(language)}</dd>
          </div>
        ))}
      </dl>
      {selection.runs_without_data > 0 && (
        <p className="mt-2 text-[12.5px] text-unverified">
          {translatePlural(language, 'overview.selection.missing', selection.runs_without_data, { count: selection.runs_without_data })}
        </p>
      )}
    </>
  )
}

function Filtering({ data }: { data: QualityOverview }) {
  const { language, t } = useLanguage()
  const filtering = data.filtering
  if (filtering === null) return <p className="text-[14px] text-muted">{t('overview.filtering.local')}</p>
  const metric = (value: number | null | undefined) => (value === null || value === undefined ? '–' : formatPercent(value, language))
  return (
    <>
      {filtering.compared === 0 ? (
        <p className="text-[14px] text-muted">{t('overview.filtering.none')}</p>
      ) : (
        <>
          {filtering.small_sample && (
            <p className="rounded-control bg-unverified/10 px-3.5 py-2.5 text-[13px] text-unverified">
              {t('overview.filtering.small', { count: filtering.compared, min: filtering.min_sample })}
            </p>
          )}
          <dl className={`mt-3 grid grid-cols-3 gap-3 ${filtering.small_sample ? 'opacity-70' : ''}`}>
            <Metric label={t('overview.filtering.precision')} value={metric(filtering.precision)} />
            <Metric label={t('overview.filtering.recall')} value={metric(filtering.recall)} />
            <Metric label={t('overview.filtering.falseReliable')} value={String(filtering.false_reliable ?? '–')} />
          </dl>
        </>
      )}
      <MoreLink to={`/quality/annotate?lang=${language}`}>{t('overview.filtering.link')}</MoreLink>
    </>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[12.5px] text-muted">{label}</dt>
      <dd className="text-[20px] font-bold tabular-nums">{value}</dd>
    </div>
  )
}

function Card({ title, source, days, children }: { title: string; source: string[]; days: number; children: ReactNode }) {
  const { t } = useLanguage()
  return (
    <section className="flex flex-col rounded-card bg-surface p-5 shadow-card sm:p-6">
      <h3 className="text-[16px] font-bold">{title}</h3>
      <div className="mt-3 flex-1">{children}</div>
      <p className="mt-4 text-[12px] text-faint">{t('overview.source', { source: source.join(', '), days })}</p>
    </section>
  )
}

function MoreLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="mt-3 inline-flex items-center gap-1 text-[13px] font-semibold text-accent hover:underline">
      {children}
      <ArrowRight size={14} aria-hidden />
    </Link>
  )
}

function formatNumber(value: number, language: string): string {
  return value.toLocaleString(language, { maximumFractionDigits: 1 })
}
