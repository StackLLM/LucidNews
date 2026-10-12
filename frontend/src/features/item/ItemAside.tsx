import { ArrowUpRight, BadgeCheck, Check, ChevronRight, Link2, MessageSquare, Quote } from 'lucide-react'
import { AnimatePresence, m } from 'motion/react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { reliabilityStyles } from '../../design/ReliabilityBadge'
import type { ItemDetail, Reliability, Run } from '../../lib/api'
import { capitalize, formatEditionDate, formatTime } from '../../lib/format'
import { labelHintKey, labelKey, tierKey, useLanguage, type MessageKey } from '../../lib/i18n'

/** The "how much can I trust this" card: label, publisher, claim, corroboration. */
export function ReliabilityPanel({ item, reliability }: { item: ItemDetail; reliability: Reliability }) {
  const { t } = useLanguage()
  const { icon: Icon, tone } = reliabilityStyles[reliability.label]

  return (
    <section aria-labelledby="reliability-title" className="glass rounded-card p-6">
      <h2 id="reliability-title" className="text-[15px] font-bold">
        {t('edition.reliability')}
      </h2>
      <div className="mt-4 flex items-center gap-3">
        <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-full ring-1 ring-inset ${tone}`}>
          <Icon size={20} strokeWidth={2.25} aria-hidden />
        </span>
        <div>
          <p className="text-[22px] leading-tight font-bold">{t(labelKey(reliability.label))}</p>
          <p className="text-[13px] leading-snug text-muted">{t(labelHintKey(reliability.label))}</p>
        </div>
      </div>

      <dl className="mt-5 space-y-4 border-t border-ink/[0.06] pt-5 text-[14px]">
        <div>
          <dt className="text-[12px] font-semibold uppercase tracking-[0.08em] text-faint">{t('detail.publisher')}</dt>
          <dd className="mt-1 flex items-center gap-1.5 font-semibold">
            {reliability.source_domain}
            {reliability.source_tier === 'official' && <BadgeCheck size={16} className="text-reliable" aria-hidden />}
          </dd>
          <dd className="text-[13px] text-muted">{t(tierKey(reliability.source_tier))}</dd>
        </div>

        <div>
          <dt className="text-[12px] font-semibold uppercase tracking-[0.08em] text-faint">{t('detail.claim')}</dt>
          <dd className="mt-1 font-semibold">{item.claim ? t(`claim.${item.claim.status}` as MessageKey) : t('detail.notAssessed')}</dd>
          {item.claim?.evidence && (
            <dd className="mt-2 rounded-control bg-surface/70 p-3 text-[13px] leading-relaxed text-ink/75">
              <span className="mb-1 flex items-center gap-1.5 text-[11.5px] font-semibold text-faint">
                <Quote size={12} aria-hidden />
                {t('detail.evidence')}
              </span>
              <span lang="en">{item.claim.evidence}</span>
            </dd>
          )}
        </div>

        <div>
          <dt className="text-[12px] font-semibold uppercase tracking-[0.08em] text-faint">{t('detail.corroboration')}</dt>
          {reliability.corroborated_by.length > 0 ? (
            <dd className="mt-1.5 flex flex-wrap gap-1.5">
              {reliability.corroborated_by.map((domain) => (
                <span key={domain} className="rounded-full bg-surface/80 px-2.5 py-1 text-[12.5px] font-medium">
                  {domain}
                </span>
              ))}
            </dd>
          ) : (
            <dd className="mt-1 text-[13px] text-muted">{t('detail.noCorroboration')}</dd>
          )}
        </div>
      </dl>
    </section>
  )
}

/** Open the original, the discussion, or copy a shareable link. */
export function ItemActions({ item }: { item: ItemDetail }) {
  const { t } = useLanguage()
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), 2000)
    return () => window.clearTimeout(timer)
  }, [copied])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
    } catch {
      // Clipboard refused (permissions, insecure origin): the address bar still has the link.
    }
  }

  return (
    <section aria-label={t('detail.read')} className="space-y-3">
      <a
        href={item.url}
        target="_blank"
        rel="noreferrer noopener"
        className="group flex w-full items-center justify-center gap-2 rounded-[16px] bg-accent px-5 py-4 text-[15px] font-semibold text-on-fill shadow-accent transition-all duration-150 ease-soft hover:-translate-y-0.5 hover:bg-accent-deep active:translate-y-0 active:scale-[0.99]"
      >
        {t('detail.openSource')}
        <ArrowUpRight size={17} aria-hidden className="transition-transform duration-150 ease-soft group-hover:-translate-y-px group-hover:translate-x-px" />
      </a>
      <div className="grid grid-cols-2 gap-3">
        {item.discussion_url ? (
          <a
            href={item.discussion_url}
            target="_blank"
            rel="noreferrer noopener"
            className="glass flex items-center justify-center gap-2 rounded-[16px] px-3 py-3.5 text-[14px] font-semibold text-accent transition-all duration-150 ease-soft hover:-translate-y-0.5 hover:bg-surface"
          >
            <MessageSquare size={16} aria-hidden />
            {t('detail.discussion')}
          </a>
        ) : (
          <span />
        )}
        {/* The label is inside the animated span below. */}
        {/* oxlint-disable-next-line jsx-a11y/control-has-associated-label */}
        <button
          type="button"
          onClick={copy}
          className="glass flex items-center justify-center gap-2 rounded-[16px] px-3 py-3.5 text-[14px] font-semibold text-accent transition-all duration-150 ease-soft hover:-translate-y-0.5 hover:bg-surface active:scale-[0.98]"
        >
          <AnimatePresence mode="wait" initial={false}>
            <m.span
              key={copied ? 'done' : 'copy'}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
              className="flex items-center gap-2"
            >
              {copied ? <Check size={16} aria-hidden /> : <Link2 size={16} aria-hidden />}
              {copied ? t('detail.copied') : t('detail.copy')}
            </m.span>
          </AnimatePresence>
        </button>
      </div>
      <p role="status" aria-live="polite" className="sr-only">
        {copied ? t('detail.copied') : ''}
      </p>
    </section>
  )
}

/** Editions that published this item (an item can appear in several runs). */
export function ItemEditions({ editions }: { editions: Run[] }) {
  const { language, t } = useLanguage()
  return (
    <section aria-labelledby="item-editions" className="glass rounded-card p-6">
      <h2 id="item-editions" className="text-[15px] font-bold">
        {t('detail.editions')}
      </h2>
      {editions.length === 0 ? (
        <p className="mt-2 text-[13px] text-muted">{t('detail.noEdition')}</p>
      ) : (
        <ul className="mt-3 space-y-1">
          {editions.map((edition) => (
            <li key={edition.id}>
              <Link
                to={{ pathname: `/editions/${edition.id}`, search: `?lang=${language}` }}
                className="group flex items-center justify-between rounded-control px-3 py-2.5 text-[14px] transition-colors duration-150 hover:bg-surface"
              >
                <span>
                  <span className="font-medium">{capitalize(formatEditionDate(edition.started_at, language))}</span>
                  <span className="ml-2 text-muted tabular-nums">{formatTime(edition.started_at, language)}</span>
                </span>
                <ChevronRight size={15} aria-hidden className="text-faint transition-transform duration-150 ease-soft group-hover:translate-x-0.5" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
