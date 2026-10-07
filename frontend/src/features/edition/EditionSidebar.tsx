import { motion } from 'motion/react'
import { reliabilityStyles } from '../../design/ReliabilityBadge'
import { reliabilityLabels, type Edition } from '../../lib/api'
import { labelHintKey, labelKey, useLanguage } from '../../lib/i18n'
import { riseIn, useMotionPreference } from '../../lib/motion'

/** Floating side column: section index and the edition's reliability breakdown. */
export function EditionSidebar({ edition }: { edition: Edition }) {
  const { t } = useLanguage()
  const { enabled } = useMotionPreference()
  const items = edition.sections.flatMap((section) => section.items)
  const counts = Object.fromEntries(
    reliabilityLabels.map((label) => [label, items.filter((item) => item.reliability?.label === label).length]),
  )

  return (
    <motion.aside variants={riseIn} className="space-y-5 self-start xl:sticky xl:top-28">
      <nav aria-labelledby="edition-index" className="glass rounded-card p-6">
        <h2 id="edition-index" className="text-[15px] font-bold">
          {t('edition.inThisEdition')}
        </h2>
        <ul className="mt-4 space-y-1">
          {edition.sections.map((section) => (
            <li key={section.profile}>
              <a
                href={`#section-${section.profile}`}
                className="group flex items-center justify-between rounded-control px-3 py-2.5 text-[14px] font-medium text-ink/80 transition-colors duration-150 hover:bg-white hover:text-ink"
              >
                {section.name}
                <span className="grid h-6 min-w-6 place-items-center rounded-full bg-accent-soft px-1.5 text-[12px] font-bold text-accent tabular-nums transition-colors duration-150 group-hover:bg-accent group-hover:text-white">
                  {section.items.length}
                </span>
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <section aria-labelledby="edition-reliability" className="glass rounded-card p-6">
        <h2 id="edition-reliability" className="text-[15px] font-bold">
          {t('edition.reliability')}
        </h2>
        <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{t('edition.reliabilityHint')}</p>

        <div className="mt-5 flex h-2 overflow-hidden rounded-full bg-ink/5" aria-hidden>
          {reliabilityLabels.map((label) =>
            counts[label] ? (
              <motion.span
                key={label}
                initial={enabled ? { width: 0 } : false}
                animate={{ width: `${(counts[label] / Math.max(items.length, 1)) * 100}%` }}
                transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1], delay: 0.3 }}
                className={`${reliabilityStyles[label].dot} h-full first:rounded-l-full last:rounded-r-full`}
              />
            ) : null,
          )}
        </div>

        <ul className="mt-5 space-y-3.5">
          {reliabilityLabels.map((label) => {
            const Icon = reliabilityStyles[label].icon
            return (
              <li key={label} className="flex gap-3">
                <span className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full ring-1 ring-inset ${reliabilityStyles[label].tone}`}>
                  <Icon size={14} strokeWidth={2.25} aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex items-baseline justify-between gap-2 text-[14px] font-semibold">
                    {t(labelKey(label))}
                    <span className="text-muted tabular-nums">{counts[label]}</span>
                  </p>
                  <p className="text-[12.5px] leading-snug text-muted">{t(labelHintKey(label))}</p>
                </div>
              </li>
            )
          })}
        </ul>
      </section>
    </motion.aside>
  )
}
