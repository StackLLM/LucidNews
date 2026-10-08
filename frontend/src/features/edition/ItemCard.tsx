import { ArrowUpRight, ChevronDown, Clock, FileText, MessageSquare, TriangleAlert } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useId, useState } from 'react'
import { Link } from 'react-router'
import { ReliabilityBadge } from '../../design/ReliabilityBadge'
import type { EditionItem } from '../../lib/api'
import { formatItemTime, formatScore, hostOf, itemPath, sourceName } from '../../lib/format'
import { categoryLabel, labelHintKey, tierKey, useLanguage, type MessageKey } from '../../lib/i18n'
import { expand, riseIn } from '../../lib/motion'

const importanceTone: Record<string, string> = {
  critical: 'bg-ink text-white',
  high: 'bg-accent-soft text-accent',
  medium: 'bg-ink/5 text-muted',
  low: 'bg-ink/5 text-faint',
}

export function ItemCard({ item, editionId }: { item: EditionItem; editionId?: string }) {
  const { language, t } = useLanguage()
  const [open, setOpen] = useState(false)
  const detailsId = useId()
  const reliability = item.reliability
  const unconfirmed = reliability?.label === 'unverified' || reliability?.label === 'rumor'

  return (
    <motion.article
      variants={riseIn}
      id={`item-${item.id}`}
      className="group scroll-mt-28 rounded-card bg-surface p-5 shadow-card ring-1 ring-ink/[0.03] transition-[box-shadow,translate] duration-300 ease-soft hover:-translate-y-0.5 hover:shadow-card-hover sm:p-8"
    >
      <div className="flex flex-wrap items-center gap-2">
        {item.importance && (
          <span className={`rounded-full px-2.5 py-1 text-[12px] font-semibold ${importanceTone[item.importance]}`}>
            {t(`importance.${item.importance}` as MessageKey)}
          </span>
        )}
        <span className="text-[13px] font-semibold text-muted tabular-nums" aria-label={`${t('item.score')} ${formatScore(item.score)}/10`}>
          {formatScore(item.score)}
          <span className="text-faint">/10</span>
        </span>
        {reliability && (
          <span className="ml-auto flex items-center gap-2">
            <span className="hidden text-[12.5px] text-faint sm:inline">{t(tierKey(reliability.source_tier))}</span>
            <ReliabilityBadge label={reliability.label} />
          </span>
        )}
      </div>

      <h3 className="mt-4 font-serif text-[23px] leading-[1.22] font-medium tracking-[-0.005em] text-ink sm:text-[26px]">
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer noopener"
          className="decoration-accent/30 decoration-2 underline-offset-4 transition-colors duration-150 hover:text-accent hover:underline"
        >
          {item.title}
        </a>
      </h3>

      {unconfirmed && reliability && (
        <p
          className={`mt-3 flex items-start gap-2 rounded-control px-3 py-2 text-[13.5px] ${
            reliability.label === 'rumor' ? 'bg-rumor/[0.07] text-rumor' : 'bg-unverified/[0.07] text-unverified'
          }`}
        >
          <TriangleAlert size={15} className="mt-0.5 shrink-0" aria-hidden />
          {t(labelHintKey(reliability.label))}
        </p>
      )}

      <p className="mt-3 font-serif text-[17.5px] leading-[1.6] text-ink/80">{item.summary}</p>

      {!item.translated && <p className="mt-2 text-[13px] italic text-faint">{t('item.notTranslated')}</p>}

      {item.categories.length > 0 && (
        <ul className="mt-5 flex flex-wrap gap-1.5">
          {item.categories.map((category) => (
            <li key={category} className="rounded-full bg-canvas px-2.5 py-1 text-[12px] font-medium text-muted">
              {categoryLabel(language, category)}
            </li>
          ))}
        </ul>
      )}

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={detailsId}
            key="details"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={expand}
            className="overflow-hidden"
          >
            <div className="mt-6 grid gap-5 border-t border-line pt-6 md:grid-cols-2">
              {item.sections.map((section) => (
                <section key={section.id}>
                  <h4 className="text-[12px] font-bold uppercase tracking-[0.08em] text-faint">{section.title}</h4>
                  <p className="mt-1.5 text-[14.5px] leading-[1.65] text-ink/75">{section.content}</p>
                </section>
              ))}
              {reliability && reliability.corroborated_by.length > 0 && (
                <p className="text-[13.5px] text-muted md:col-span-2">
                  {t('item.corroborated', { count: reliability.corroborated_by.length })} —{' '}
                  {reliability.corroborated_by.join(', ')}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <footer className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line pt-4 text-[13px] text-muted">
        <span className="font-semibold text-ink/70">{sourceName(item.source_type)}</span>
        <span className="flex items-center gap-1.5">
          <Clock size={13} aria-hidden />
          <time dateTime={item.published_at}>{formatItemTime(item.published_at, language)}</time>
        </span>
        {item.discussion_url && (
          <a
            href={item.discussion_url}
            target="_blank"
            rel="noreferrer noopener"
            className="flex items-center gap-1.5 transition-colors duration-150 hover:text-accent"
          >
            <MessageSquare size={13} aria-hidden />
            {t('item.discussion')}
          </a>
        )}
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer noopener"
          aria-label={`${t('item.open')} (${hostOf(item.url)})`}
          className="group/link flex items-center gap-1 transition-colors duration-150 hover:text-accent"
        >
          {hostOf(item.url)}
          <ArrowUpRight
            size={13}
            aria-hidden
            className="transition-transform duration-150 ease-soft group-hover/link:-translate-y-px group-hover/link:translate-x-px"
          />
        </a>

        <span className="ml-auto flex items-center gap-2">
          <Link
            to={itemPath(item.id, language, editionId)}
            className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold text-ink/70 transition-colors duration-150 hover:bg-canvas hover:text-ink"
          >
            <FileText size={14} aria-hidden />
            {t('item.details')}
          </Link>
        {item.sections.length > 0 && (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={detailsId}
            onClick={() => setOpen((value) => !value)}
            className="flex items-center gap-1.5 rounded-full bg-accent-soft px-3.5 py-1.5 text-[13px] font-semibold text-accent transition-all duration-150 ease-soft hover:bg-accent hover:text-white active:scale-95"
          >
            {t(open ? 'item.readLess' : 'item.readMore')}
            <ChevronDown
              size={14}
              aria-hidden
              className={`transition-transform duration-250 ease-soft ${open ? 'rotate-180' : ''}`}
            />
          </button>
        )}
        </span>
      </footer>
    </motion.article>
  )
}
