import { CalendarDays } from 'lucide-react'
import { motion } from 'motion/react'
import { CountUp } from '../../design/CountUp'
import type { Edition } from '../../lib/api'
import { capitalize, formatEditionDate } from '../../lib/format'
import { isLanguage, useLanguage } from '../../lib/i18n'
import { riseIn } from '../../lib/motion'

/** The edition banner: accent card with soft circles, date and run figures. */
export function EditionHero({ edition, archived = false }: { edition: Edition; archived?: boolean }) {
  const { language, t } = useLanguage()
  const stats = [
    { value: edition.fetched_count, label: t('edition.analyzed') },
    { value: edition.selected_count, label: t('edition.selected') },
    { value: edition.sections.length, label: t('edition.sections') },
  ]

  return (
    <motion.section
      variants={riseIn}
      className="relative isolate overflow-hidden rounded-card bg-gradient-to-br from-accent to-accent-deep px-6 py-8 text-white shadow-[0_30px_70px_-30px_rgb(76_63_216/0.6)] sm:px-10 sm:py-10"
    >
      <span aria-hidden className="absolute -right-24 -top-28 -z-10 h-80 w-80 rounded-full bg-white/[0.07]" />
      <span aria-hidden className="absolute -bottom-36 right-40 -z-10 h-72 w-72 rounded-full bg-white/[0.05]" />
      <span aria-hidden className="absolute -left-20 bottom-[-9rem] -z-10 h-64 w-64 rounded-full bg-white/[0.04]" />

      <p className="flex items-center gap-2 text-sm font-semibold text-white/75">
        <CalendarDays size={16} aria-hidden />
        {t(archived ? 'edition.archived' : 'edition.kicker')}
      </p>
      <h1 className="mt-3 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em] sm:text-[44px]">
        {capitalize(formatEditionDate(edition.started_at, isLanguage(edition.language) ? edition.language : language))}
      </h1>

      <dl className="mt-8 flex flex-wrap gap-3">
        {stats.map(({ value, label }) => (
          <div
            key={label}
            className="flex items-baseline gap-2 rounded-2xl border border-white/15 bg-white/10 px-4 py-2.5 backdrop-blur-sm"
          >
            <dt className="sr-only">{label}</dt>
            <dd className="text-2xl font-bold">
              <CountUp value={value} />
            </dd>
            <span aria-hidden className="text-sm text-white/75">
              {label}
            </span>
          </div>
        ))}
      </dl>
    </motion.section>
  )
}
