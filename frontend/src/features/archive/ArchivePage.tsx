import 'react-day-picker/style.css'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Clock, Hourglass } from 'lucide-react'
import { motion } from 'motion/react'
import { useMemo, useState } from 'react'
import { DayPicker } from 'react-day-picker'
import { enGB, fr } from 'react-day-picker/locale'
import { Link } from 'react-router'
import { ApiErrorCard, PageHeader, PageSkeleton } from '../../design/PageState'
import { fetchEditions, type Run } from '../../lib/api'
import { capitalize, dayKey, formatEditionDate, formatTime } from '../../lib/format'
import { translatePlural, useLanguage } from '../../lib/i18n'
import { listStagger, riseIn, useMotionPreference } from '../../lib/motion'

export function ArchivePage() {
  const query = useQuery({ queryKey: ['editions'], queryFn: ({ signal }) => fetchEditions(signal) })
  if (query.isPending) return <PageSkeleton />
  if (query.isError) return <ApiErrorCard error={query.error} onRetry={() => query.refetch()} />
  return <ArchiveView runs={query.data} />
}

function ArchiveView({ runs }: { runs: Run[] }) {
  const { language, t } = useLanguage()
  const { enabled } = useMotionPreference()
  const [selectedDay, setSelectedDay] = useState<Date | undefined>()

  const byDay = useMemo(() => {
    const groups = new Map<string, Run[]>()
    for (const run of runs) {
      const key = dayKey(run.started_at)
      groups.set(key, [...(groups.get(key) ?? []), run])
    }
    return groups
  }, [runs])
  const editionDays = useMemo(() => runs.map((run) => new Date(run.started_at)), [runs])

  const visibleDays = selectedDay
    ? [...byDay.entries()].filter(([key]) => key === dayKey(selectedDay))
    : [...byDay.entries()]

  return (
    <motion.div variants={listStagger} initial={enabled ? 'hidden' : false} animate="visible" className="space-y-8">
      <PageHeader title={t('archive.title')} subtitle={t('archive.subtitle')} />

      <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)] lg:gap-8">
        <motion.section
          variants={riseIn}
          aria-label={t('archive.calendar')}
          className="glass self-start rounded-card p-5 lg:sticky lg:top-28"
        >
          <DayPicker
            className="lucid-calendar mx-auto w-fit"
            mode="single"
            locale={language === 'fr' ? fr : enGB}
            weekStartsOn={1}
            defaultMonth={editionDays[0]}
            selected={selectedDay}
            onSelect={setSelectedDay}
            disabled={(date) => !byDay.has(dayKey(date))}
            modifiers={{ hasEdition: editionDays }}
            modifiersClassNames={{ hasEdition: 'has-edition' }}
          />
          <div className="mt-3 flex items-center justify-between border-t border-ink/[0.06] px-1 pt-4 text-[13px]">
            <span className="text-muted">{t('archive.count', { count: runs.length })}</span>
            {selectedDay && (
              <button
                type="button"
                onClick={() => setSelectedDay(undefined)}
                className="rounded-full bg-accent-soft px-3 py-1 font-semibold text-accent transition-colors duration-150 hover:bg-accent hover:text-white"
              >
                {t('archive.showAll')}
              </button>
            )}
          </div>
        </motion.section>

        <div className="min-w-0 space-y-8">
          {runs.length === 0 && <p className="text-muted">{t('archive.empty')}</p>}
          {visibleDays.map(([key, dayRuns]) => (
            <motion.section key={key} variants={riseIn} aria-labelledby={`day-${key}`} className="space-y-3">
              <h2
                id={`day-${key}`}
                className="flex items-center gap-3 px-1 text-[13px] font-bold uppercase tracking-[0.1em] text-muted"
              >
                {capitalize(formatEditionDate(dayRuns[0].started_at, language))}
                <span className="h-px flex-1 bg-ink/10" />
              </h2>
              <ul className="space-y-3">
                {dayRuns.map((run) => (
                  <li key={run.id}>
                    <EditionRow run={run} />
                  </li>
                ))}
              </ul>
            </motion.section>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

function EditionRow({ run }: { run: Run }) {
  const { language, t } = useLanguage()
  const share = run.fetched_count ? run.selected_count / run.fetched_count : 0
  return (
    <Link
      to={{ pathname: `/editions/${run.id}`, search: `?lang=${language}` }}
      className="group flex items-center gap-4 rounded-card bg-surface p-4 shadow-card ring-1 ring-ink/[0.03] transition-[box-shadow,translate] duration-300 ease-soft hover:-translate-y-0.5 hover:shadow-card-hover sm:gap-5 sm:p-5"
    >
      <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent">
        <Clock size={20} aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[16px] font-bold tabular-nums">{formatTime(run.started_at, language)}</p>
        <p className="mt-0.5 text-[13.5px] text-muted">
          {translatePlural(language, 'archive.ratio', run.selected_count, {
            selected: run.selected_count,
            fetched: run.fetched_count,
          })}
        </p>
        {run.ai_limit && (
          <p className="mt-1.5 inline-flex items-center gap-1.5 rounded-full bg-unverified/10 px-2.5 py-0.5 text-[12px] font-semibold text-unverified">
            <Hourglass size={12} aria-hidden />
            {t('archive.quota')}
          </p>
        )}
        {/* Meter: selected share of collected items. */}
        <span className="mt-2.5 block h-1.5 w-full max-w-60 overflow-hidden rounded-full bg-accent-soft" aria-hidden>
          <span className="block h-full rounded-full bg-accent" style={{ width: `${Math.max(share * 100, 3)}%` }} />
        </span>
      </div>
      <span className="flex items-center gap-1.5 text-[13px] font-semibold text-accent">
        <span className="hidden sm:inline">{t('archive.open')}</span>
        <ArrowRight
          size={16}
          aria-hidden
          className="transition-transform duration-150 ease-soft group-hover:translate-x-0.5"
        />
      </span>
    </Link>
  )
}
