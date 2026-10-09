import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowLeft, ChevronRight, Hash, Hourglass, TriangleAlert } from 'lucide-react'
import { motion } from 'motion/react'
import { Link, useParams, useSearchParams } from 'react-router'
import { ApiErrorCard, PageSkeleton } from '../../design/PageState'
import { ReliabilityBadge } from '../../design/ReliabilityBadge'
import { fetchItem, type ItemDetail } from '../../lib/api'
import { capitalize, formatEditionDate, formatItemTime, formatScore, hostOf, sourceName } from '../../lib/format'
import { categoryLabel, isLanguage, labelHintKey, tierKey, useLanguage, type MessageKey } from '../../lib/i18n'
import { listStagger, riseIn, useMotionPreference } from '../../lib/motion'
import { ItemActions, ItemEditions, ReliabilityPanel } from './ItemAside'

export function ItemPage() {
  const { itemId = '' } = useParams()
  const { language, t } = useLanguage()
  const query = useQuery({
    queryKey: ['item', itemId, language],
    queryFn: ({ signal }) => fetchItem(itemId, language, signal),
    placeholderData: keepPreviousData,
  })

  if (query.isPending) return <PageSkeleton blocks={2} />
  if (query.isError)
    return <ApiErrorCard error={query.error} onRetry={() => query.refetch()} notFound={t('detail.notFound')} />
  return <ItemView key={query.data.id} item={query.data} />
}

function ItemView({ item }: { item: ItemDetail }) {
  const { language, t } = useLanguage()
  const { enabled } = useMotionPreference()
  const [params] = useSearchParams()
  const from = params.get('from')
  const backTo = { pathname: from ? `/editions/${from}` : '/', search: `?lang=${language}` }
  // Dates follow the language the content is written in (kept while a switch loads).
  const contentLanguage = isLanguage(item.language) ? item.language : language
  const fromEdition = item.editions.find((edition) => edition.id === from) ?? item.editions[0]
  const reliability = item.reliability
  // A skipped item has its own notice instead of the generic "unverified" hint.
  const unconfirmed = !item.ai_skipped && (reliability?.label === 'unverified' || reliability?.label === 'rumor')

  return (
    <motion.div variants={listStagger} initial={enabled ? 'hidden' : false} animate="visible" className="space-y-6">
      <motion.nav variants={riseIn} aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 px-1 text-[14px]">
        <Link
          to={backTo}
          className="group flex items-center gap-1.5 font-semibold text-accent transition-colors duration-150 hover:text-accent-deep"
        >
          <ArrowLeft size={15} aria-hidden className="transition-transform duration-150 ease-soft group-hover:-translate-x-0.5" />
          {fromEdition ? capitalize(formatEditionDate(fromEdition.started_at, contentLanguage)) : t('detail.back')}
        </Link>
        <ChevronRight size={14} aria-hidden className="text-faint" />
        <span className="text-muted">{t('detail.crumb')}</span>
      </motion.nav>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px] xl:gap-8">
        <motion.article variants={riseIn} className="min-w-0 rounded-card bg-surface p-5 shadow-card sm:p-9">
          {/* Identity row: who published it. */}
          <header className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <span
                aria-hidden
                className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-accent-soft text-[18px] font-bold uppercase text-accent"
              >
                {hostOf(item.url).charAt(0)}
              </span>
              <div>
                <p className="text-[16px] font-bold">{hostOf(item.url)}</p>
                <p className="text-[13.5px] text-muted">
                  {sourceName(item.source_type)}
                  {item.author ? ` · ${item.author}` : ''}
                </p>
              </div>
            </div>
            <dl className="flex gap-2 text-[13.5px] text-muted sm:block sm:text-right">
              <dt className="sr-only">{t('detail.published')}</dt>
              <dd>
                <time dateTime={item.published_at}>{formatItemTime(item.published_at, contentLanguage)}</time>
              </dd>
              <dt className="sr-only">{t('detail.section')}</dt>
              <dd>
                <span aria-hidden className="sm:hidden">· </span>
                {item.profile_name}
              </dd>
            </dl>
          </header>

          {/* Key facts band (nothing to show when the AI did not analyze the item). */}
          {!item.ai_skipped && (
            <div className="relative isolate mt-7 overflow-hidden rounded-[20px] bg-gradient-to-br from-accent to-accent-deep px-6 py-5 text-white">
              <span aria-hidden className="absolute -right-16 -top-20 -z-10 h-56 w-56 rounded-full bg-white/[0.08]" />
              <span aria-hidden className="absolute -bottom-24 right-32 -z-10 h-44 w-44 rounded-full bg-white/[0.05]" />
              <dl className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
                <div>
                  <dt className="text-[13px] font-semibold text-white/70">{t('detail.score')}</dt>
                  <dd className="mt-0.5 flex items-baseline gap-2">
                    <span className="text-[30px] leading-none font-bold">{formatScore(item.score)}</span>
                    <span className="text-white/60">/10</span>
                    {item.importance && (
                      <span className="ml-1 rounded-full bg-white/15 px-2.5 py-0.5 text-[12px] font-semibold">
                        {t(`importance.${item.importance}` as MessageKey)}
                      </span>
                    )}
                  </dd>
                </div>
                {item.categories.length > 0 && (
                  <div className="sm:text-right">
                    <dt className="sr-only">{t('detail.categories')}</dt>
                    <dd className="flex flex-wrap gap-1.5 sm:justify-end">
                      {item.categories.map((category) => (
                        <span key={category} className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1 text-[12px] font-medium">
                          {categoryLabel(language, category)}
                        </span>
                      ))}
                    </dd>
                  </div>
                )}
              </dl>
            </div>
          )}

          <h1 className="mt-8 font-serif text-[30px] leading-[1.15] font-medium tracking-[-0.01em] sm:text-[38px]">
            {item.title}
          </h1>

          {/* Below xl the reliability panel sits after the text: keep the label next to the title. */}
          {reliability && (
            <p className="mt-4 flex flex-wrap items-center gap-2 text-[13px] text-muted xl:hidden">
              <ReliabilityBadge label={reliability.label} />
              {t(tierKey(reliability.source_tier))} · {reliability.source_domain}
            </p>
          )}

          {unconfirmed && reliability && (
            <p
              className={`mt-4 flex items-start gap-2 rounded-control px-3.5 py-2.5 text-[14px] ${
                reliability.label === 'rumor' ? 'bg-rumor/[0.07] text-rumor' : 'bg-unverified/[0.07] text-unverified'
              }`}
            >
              <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden />
              {t(labelHintKey(reliability.label))}
            </p>
          )}

          {item.ai_skipped ? (
            <p className="mt-5 flex items-start gap-2.5 rounded-control bg-unverified/[0.07] px-4 py-3 text-[14.5px] leading-relaxed text-unverified">
              <Hourglass size={16} className="mt-0.5 shrink-0" aria-hidden />
              {t('unanalyzed.detail')}
            </p>
          ) : (
            <>
              <p className="mt-5 font-serif text-[19px] leading-[1.65] text-ink/85">{item.summary}</p>
              {!item.translated && <p className="mt-2 text-[13px] italic text-faint">{t('item.notTranslated')}</p>}
            </>
          )}

          {item.sections.length > 0 && (
            <div className="mt-8 space-y-7 border-t border-line pt-8">
              {item.sections.map((section) => (
                <section key={section.id} aria-labelledby={`section-${section.id}`}>
                  <h2
                    id={`section-${section.id}`}
                    className="text-[12px] font-bold uppercase tracking-[0.1em] text-faint"
                  >
                    {section.title}
                  </h2>
                  <p className="mt-2 font-serif text-[17px] leading-[1.7] text-ink/80">{section.content}</p>
                </section>
              ))}
            </div>
          )}

          {item.tags.length > 0 && (
            <ul aria-label={t('detail.tags')} className="mt-8 flex flex-wrap gap-1.5 border-t border-line pt-6">
              {item.tags.map((tag) => (
                <li key={tag} className="flex items-center gap-0.5 rounded-full bg-canvas px-2.5 py-1 text-[12px] font-medium text-muted">
                  <Hash size={11} aria-hidden />
                  {tag}
                </li>
              ))}
            </ul>
          )}
        </motion.article>

        <motion.aside variants={riseIn} className="space-y-5 self-start xl:sticky xl:top-28">
          {reliability && <ReliabilityPanel item={item} reliability={reliability} />}
          <ItemActions item={item} />
          <ItemEditions editions={item.editions} />
        </motion.aside>
      </div>
    </motion.div>
  )
}
