import { useQuery } from '@tanstack/react-query'
import { ShieldAlert, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router'
import { ApiErrorCard, PageSkeleton } from '../../design/PageState'
import { claimStatuses, fetchQualityReport, type Comparison, type QualityReport } from '../../lib/api'
import { formatPercent, itemPath } from '../../lib/format'
import { useLanguage, type MessageKey } from '../../lib/i18n'
import { EmptyCard } from './AnnotateView'

export function ResultsView() {
  const { t } = useLanguage()
  const query = useQuery({ queryKey: ['quality-report'], queryFn: ({ signal }) => fetchQualityReport(signal) })
  if (query.isPending) return <PageSkeleton blocks={2} />
  if (query.isError) return <ApiErrorCard error={query.error} onRetry={() => query.refetch()} />
  if (query.data.compared === 0) return <EmptyCard text={t('quality.emptyResults')} />
  return <Results report={query.data} />
}

function Results({ report }: { report: QualityReport }) {
  const { language, t } = useLanguage()
  const pct = (value: number | null) => (value === null ? '–' : formatPercent(value, language))
  const falseReliable = report.items.filter((item) => item.issues.includes('false_reliable'))
  const differing = report.items.filter((item) => item.issues.length > 0)

  const tiles = [
    { label: t('quality.selection'), value: pct(report.selection.f1), hint: t('quality.selectionHint') },
    {
      label: t('quality.importance'),
      value: pct(report.importance.exact),
      hint: t('quality.importanceHint', { within: pct(report.importance.within_one) }),
    },
    { label: t('quality.categories'), value: pct(report.categories.f1), hint: t('quality.categoriesHint') },
    { label: t('quality.claim'), value: pct(report.claim.accuracy), hint: t('quality.claimHint') },
  ]

  return (
    <div className="space-y-6">
      {(report.small_sample || report.missing.length > 0) && (
        <p className="flex items-start gap-2 rounded-control bg-unverified/[0.08] px-4 py-3 text-[13.5px] text-unverified">
          <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden />
          <span>
            {report.small_sample && t('quality.smallSample', { count: report.compared })}{' '}
            {report.missing.length > 0 && t('quality.missing', { count: report.missing.length })}
          </span>
        </p>
      )}

      <dl className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
        {tiles.map((tile) => (
          <div key={tile.label} className="glass rounded-card px-5 py-4">
            <dt className="text-[13px] font-medium text-muted">{tile.label}</dt>
            <dd className="mt-1 text-[30px] leading-none font-bold">{tile.value}</dd>
            <dd className="mt-2 text-[12px] leading-snug text-muted">{tile.hint}</dd>
          </div>
        ))}
        <div
          className={`col-span-2 rounded-card px-5 py-4 lg:col-span-1 ${
            report.reliability.false_reliable ? 'bg-rumor text-on-fill shadow-[0_18px_40px_-18px_rgb(180_35_60/0.6)]' : 'glass'
          }`}
        >
          <dt className={`flex items-center gap-1.5 text-[13px] font-medium ${report.reliability.false_reliable ? 'text-on-fill/85' : 'text-muted'}`}>
            <ShieldAlert size={14} aria-hidden />
            {t('quality.falseReliable')}
          </dt>
          <dd className={`mt-1 text-[30px] leading-none font-bold ${report.reliability.false_reliable ? '' : 'text-confirmed'}`}>
            {report.reliability.false_reliable}
          </dd>
          <dd className={`mt-2 text-[12px] leading-snug ${report.reliability.false_reliable ? 'text-on-fill/80' : 'text-muted'}`}>
            {t('quality.falseReliableHint')}
          </dd>
        </div>
      </dl>

      <section aria-labelledby="critical-title" className="rounded-card bg-surface p-5 shadow-card sm:p-7">
        <h2 id="critical-title" className="text-[17px] font-bold">
          {t('quality.critical')}
        </h2>
        {falseReliable.length === 0 ? (
          <p className="mt-2 text-[14px] text-confirmed">{t('quality.noCritical')}</p>
        ) : (
          <ul className="mt-4 space-y-2">
            {falseReliable.map((item) => (
              <ComparisonRow key={item.item_id} item={item} />
            ))}
          </ul>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="selection-title" className="rounded-card bg-surface p-5 shadow-card sm:p-7">
          <h2 id="selection-title" className="text-[17px] font-bold">
            {t('quality.selectionMatrix')}
          </h2>
          <table className="mt-4 w-full text-center text-[14px]">
            <thead>
              <tr className="text-[12px] text-faint">
                <td aria-hidden="true" />
                <th className="pb-2 font-semibold">{t('quality.aiKeeps')}</th>
                <th className="pb-2 font-semibold">{t('quality.aiDrops')}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th className="pr-3 text-left text-[13px] font-semibold text-muted">{t('quality.youKeep')}</th>
                <MatrixCell value={report.selection.true_positive} total={report.compared} good />
                <MatrixCell value={report.selection.false_negative} total={report.compared} />
              </tr>
              <tr>
                <th className="pr-3 text-left text-[13px] font-semibold text-muted">{t('quality.youDrop')}</th>
                <MatrixCell value={report.selection.false_positive} total={report.compared} />
                <MatrixCell value={report.selection.true_negative} total={report.compared} good />
              </tr>
            </tbody>
          </table>
        </section>

        <section aria-labelledby="claim-title" className="rounded-card bg-surface p-5 shadow-card sm:p-7">
          <h2 id="claim-title" className="text-[17px] font-bold">
            {t('quality.claimMatrix')}
          </h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-center text-[13px]">
              <thead>
                <tr className="text-[11.5px] text-faint">
                  <td aria-hidden="true" />
                  {[...claimStatuses, 'none'].map((status) => (
                    <th key={status} className="px-1 pb-2 font-semibold">
                      {status === 'none' ? t('quality.none') : t(`claimShort.${status}` as MessageKey)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {claimStatuses.map((human) => (
                  <tr key={human}>
                    <th className="pr-2 text-left text-[12.5px] font-semibold whitespace-nowrap text-muted">{t(`claim.${human}` as MessageKey)}</th>
                    {[...claimStatuses, 'none'].map((ai) => (
                      <MatrixCell key={ai} value={report.claim.confusion[human]?.[ai] ?? 0} total={report.compared} good={ai === human} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section aria-labelledby="differences-title" className="rounded-card bg-surface p-5 shadow-card sm:p-7">
        <h2 id="differences-title" className="text-[17px] font-bold">
          {t('quality.differences')} <span className="text-faint tabular-nums">· {differing.length}</span>
        </h2>
        {differing.length === 0 ? (
          <p className="mt-2 text-[14px] text-muted">{t('quality.noDifferences')}</p>
        ) : (
          <ul className="mt-4 space-y-2">
            {differing.map((item) => (
              <ComparisonRow key={item.item_id} item={item} />
            ))}
          </ul>
        )}
        <p className="mt-5 text-[12.5px] text-muted">{t('quality.cli', { command: 'uv run lucidnews-eval' })}</p>
      </section>
    </div>
  )
}

function MatrixCell({ value, total, good = false }: { value: number; total: number; good?: boolean }) {
  // Cell tint grows with the share of items; agreement cells in green, errors in red.
  const share = total ? value / total : 0
  const tint =
    value === 0 ? 'transparent' : `color-mix(in oklab, var(--color-${good ? 'confirmed' : 'rumor'}) ${Math.round(8 + share * 40)}%, var(--color-surface))`
  return (
    <td className="p-1">
      <span
        className={`block rounded-[10px] py-2.5 font-semibold tabular-nums ${value === 0 ? 'text-faint' : 'text-ink'}`}
        style={{ background: value === 0 ? 'var(--color-canvas)' : tint }}
      >
        {value}
      </span>
    </td>
  )
}

function ComparisonRow({ item }: { item: Comparison }) {
  const { language, t } = useLanguage()
  const label = (key: string | null, prefix: string) => (key ? t(`${prefix}.${key}` as MessageKey) : '–')
  return (
    <li className="rounded-control bg-canvas/70 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <Link to={itemPath(item.item_id, language)} className="min-w-0 flex-1 text-[14.5px] font-semibold hover:text-accent">
          {item.title}
        </Link>
        <span className="flex flex-wrap gap-1">
          {item.issues.map((issue) => (
            <span
              key={issue}
              className={`rounded-full px-2 py-0.5 text-[11.5px] font-semibold ${
                issue === 'false_reliable' ? 'bg-rumor text-on-fill' : 'bg-surface text-ink/70 ring-1 ring-ink/10'
              }`}
            >
              {t(`issue.${issue}` as MessageKey)}
            </span>
          ))}
        </span>
      </div>
      <dl className="mt-2.5 grid gap-x-6 gap-y-1 text-[12.5px] text-muted sm:grid-cols-2">
        <div>
          <dt className="inline font-semibold text-ink/70">{t('quality.you')} </dt>
          <dd className="inline">
            {item.human.relevant ? t('quality.yes') : t('quality.no')} · {label(item.human.importance, 'importance')} ·{' '}
            {label(item.human.claim_status, 'claim')} → {label(item.human.reliability, 'label')}
          </dd>
        </div>
        <div>
          <dt className="inline font-semibold text-ink/70">{t('quality.ai')} </dt>
          <dd className="inline">
            {item.ai.selected ? t('quality.yes') : t('quality.no')} · {label(item.ai.importance, 'importance')}
            {item.ai.score !== null ? ` (${item.ai.score.toFixed(1)})` : ''} · {label(item.ai.claim_status, 'claim')} → {label(item.ai.reliability, 'label')}
          </dd>
        </div>
      </dl>
    </li>
  )
}
