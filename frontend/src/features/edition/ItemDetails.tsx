import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, BadgeCheck, Quote, RotateCcw, TriangleAlert } from 'lucide-react'
import { reliabilityStyles } from '../../design/ReliabilityBadge'
import { fetchItem, type EditionItem, type ItemDetail } from '../../lib/api'
import { labelKey, tierKey, useLanguage, type MessageKey } from '../../lib/i18n'

/**
 * Body of an opened news card. The AI blocks come with the edition; the claim and
 * reliability details are fetched on first opening (same cache as the item page).
 */
export function ItemDetails({ item }: { item: EditionItem }) {
  const { language, t } = useLanguage()
  const query = useQuery({
    queryKey: ['item', item.id, language],
    queryFn: ({ signal }) => fetchItem(item.id, language, signal),
    staleTime: 5 * 60_000,
  })
  // The detail must describe this very card: never show another item's analysis.
  const detail = query.data && query.data.id === item.id ? query.data : undefined
  const mismatch = query.data !== undefined && detail === undefined

  return (
    <div className="mt-6 space-y-6 border-t border-line pt-6">
      {item.sections.length > 0 && (
        <div className="grid gap-5 md:grid-cols-2">
          {item.sections.map((section) => (
            <section key={section.id}>
              <h4 className="text-[12px] font-bold uppercase tracking-[0.08em] text-faint">{section.title}</h4>
              <p className="mt-1.5 text-[14.5px] leading-[1.65] text-ink/75">{section.content}</p>
            </section>
          ))}
        </div>
      )}

      {query.isPending ? (
        <div role="status" aria-live="polite" className="grid gap-3 md:grid-cols-2">
          <span className="sr-only">{t('card.loading')}</span>
          <span className="h-24 animate-shimmer rounded-control bg-canvas" />
          <span className="h-24 animate-shimmer rounded-control bg-canvas" />
        </div>
      ) : query.isError || mismatch ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-control bg-rumor/[0.06] px-4 py-3 text-[13.5px] text-rumor">
          <TriangleAlert size={15} aria-hidden className="shrink-0" />
          <span className="flex-1">{t('card.error')}</span>
          <button
            type="button"
            onClick={() => query.refetch()}
            className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 font-semibold text-ink/75 ring-1 ring-ink/10 transition-colors duration-150 hover:text-ink"
          >
            <RotateCcw size={13} aria-hidden />
            {t('state.retry')}
          </button>
        </div>
      ) : (
        detail && <Essentials item={detail} />
      )}

      <div className="flex flex-wrap gap-2.5">
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer noopener"
          className="group flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-[13.5px] font-semibold text-white shadow-accent transition-all duration-150 ease-soft hover:-translate-y-px hover:bg-accent-deep"
        >
          {t('detail.openSource')}
          <ArrowUpRight size={15} aria-hidden className="transition-transform duration-150 ease-soft group-hover:-translate-y-px group-hover:translate-x-px" />
        </a>
      </div>
    </div>
  )
}

/** Claim, publisher and corroboration: the "can I trust it" facts, compact. */
function Essentials({ item }: { item: ItemDetail }) {
  const { t } = useLanguage()
  const reliability = item.reliability
  return (
    <dl className="grid gap-3 text-[14px] md:grid-cols-2">
      <div className="rounded-control bg-canvas/70 p-4">
        <dt className="text-[12px] font-bold uppercase tracking-[0.08em] text-faint">{t('detail.claim')}</dt>
        <dd className="mt-1 font-semibold">
          {item.claim ? t(`claim.${item.claim.status}` as MessageKey) : t('detail.notAssessed')}
        </dd>
        {item.claim?.evidence && (
          <dd className="mt-2 text-[13px] leading-relaxed text-ink/70">
            <span className="mb-0.5 flex items-center gap-1.5 text-[11.5px] font-semibold text-faint">
              <Quote size={12} aria-hidden />
              {t('detail.evidence')}
            </span>
            <span lang="en">{item.claim.evidence}</span>
          </dd>
        )}
      </div>

      {reliability && (
        <div className="rounded-control bg-canvas/70 p-4">
          <dt className="text-[12px] font-bold uppercase tracking-[0.08em] text-faint">{t('edition.reliability')}</dt>
          <dd className="mt-1 flex items-center gap-2 font-semibold">
            <span className={`h-2 w-2 rounded-full ${reliabilityStyles[reliability.label].dot}`} aria-hidden />
            {t(labelKey(reliability.label))}
          </dd>
          <dd className="mt-1 flex items-center gap-1.5 text-[13px] text-muted">
            {reliability.source_domain}
            {reliability.source_tier === 'official' && <BadgeCheck size={14} className="text-reliable" aria-hidden />}
            <span aria-hidden>·</span>
            {t(tierKey(reliability.source_tier))}
          </dd>
          <dd className="mt-1 text-[13px] text-muted">
            {reliability.corroborated_by.length > 0
              ? t('card.corroboratedBy', { list: reliability.corroborated_by.join(', ') })
              : t('detail.noCorroboration')}
          </dd>
        </div>
      )}

      {item.tags.length > 0 && (
        <div className="md:col-span-2">
          <dt className="sr-only">{t('detail.tags')}</dt>
          <dd className="flex flex-wrap gap-1.5">
            {item.tags.map((tag) => (
              <span key={tag} className="rounded-full bg-white px-2.5 py-1 text-[12px] font-medium text-muted ring-1 ring-ink/[0.06]">
                #{tag}
              </span>
            ))}
          </dd>
        </div>
      )}
    </dl>
  )
}
