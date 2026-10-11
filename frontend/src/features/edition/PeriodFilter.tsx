import 'react-day-picker/style.css'
import { CalendarDays, ChevronDown } from 'lucide-react'
import { useMemo, useState } from 'react'
import { DayPicker } from 'react-day-picker'
import { enGB, fr } from 'react-day-picker/locale'
import { Popover } from 'radix-ui'
import { Segmented } from '../../design/PageState'
import type { Run } from '../../lib/api'
import { capitalize, dayKey, formatPeriod, periodBounds, type PeriodKind } from '../../lib/format'
import { useLanguage } from '../../lib/i18n'

export type PeriodChoice = { kind: PeriodKind; value: string } | null

type Mode = 'latest' | PeriodKind

const keyOf = (kind: PeriodKind, run: Run) => {
  const day = dayKey(run.started_at)
  return kind === 'day' ? day : kind === 'month' ? day.slice(0, 7) : day.slice(0, 4)
}

/**
 * Date filter of the Edition page: the latest edition, or every edition of one day, month
 * or year. Only periods that have an edition can be chosen.
 */
export function PeriodFilter({ runs, choice, onChange }: { runs: Run[]; choice: PeriodChoice; onChange: (choice: PeriodChoice) => void }) {
  const { language, t } = useLanguage()
  const [dayOpen, setDayOpen] = useState(false)
  const mode: Mode = choice?.kind ?? 'latest'

  // Newest first (the API lists runs that way).
  const options = useMemo(
    () => ({
      day: [...new Set(runs.map((run) => keyOf('day', run)))],
      month: [...new Set(runs.map((run) => keyOf('month', run)))],
      year: [...new Set(runs.map((run) => keyOf('year', run)))],
    }),
    [runs],
  )

  const switchMode = (next: Mode) => {
    if (next === 'latest') return onChange(null)
    // Keep the chosen period when the new unit contains it; else the newest one.
    const current = choice?.value ?? ''
    const kept = options[next].find((value) => current.startsWith(value) || value.startsWith(current))
    onChange({ kind: next, value: kept ?? options[next][0] })
  }

  const modes: { value: Mode; label: string }[] = [
    { value: 'latest', label: t('filter.latest') },
    { value: 'day', label: t('filter.day') },
    { value: 'month', label: t('filter.month') },
    { value: 'year', label: t('filter.year') },
  ]
  const dayDates = useMemo(() => options.day.map((value) => periodBounds('day', value)?.since).filter((date): date is Date => !!date), [options.day])

  return (
    <section aria-label={t('filter.title')} className="glass flex flex-wrap items-center gap-3 rounded-card px-4 py-3 sm:px-5">
      <span className="flex items-center gap-2 text-[14px] font-bold">
        <CalendarDays size={16} className="text-accent" aria-hidden />
        {t('filter.title')}
      </span>
      <Segmented<Mode> id="period-mode" label={t('filter.title')} value={mode} options={modes} onChange={switchMode} />

      {choice?.kind === 'day' && (
        <Popover.Root open={dayOpen} onOpenChange={setDayOpen}>
          <Popover.Trigger asChild>
            <button
              type="button"
              aria-label={t('filter.pickDay')}
              className="flex items-center gap-2 rounded-control border border-ink/10 bg-white px-3.5 py-2 text-[14px] font-semibold transition-shadow duration-150 hover:border-accent/40 focus-visible:ring-3 focus-visible:ring-accent/20"
            >
              {capitalize(formatPeriod('day', choice.value, language))}
              <ChevronDown size={14} aria-hidden className="text-muted" />
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content sideOffset={8} align="start" className="z-40 rounded-card bg-surface p-4 shadow-card-hover ring-1 ring-ink/[0.06]">
              <DayPicker
                className="lucid-calendar mx-auto w-fit"
                mode="single"
                locale={language === 'fr' ? fr : enGB}
                weekStartsOn={1}
                defaultMonth={periodBounds('day', choice.value)?.since}
                selected={periodBounds('day', choice.value)?.since}
                onSelect={(date) => {
                  if (!date) return
                  onChange({ kind: 'day', value: dayKey(date) })
                  setDayOpen(false)
                }}
                disabled={(date) => !options.day.includes(dayKey(date))}
                modifiers={{ hasEdition: dayDates }}
                modifiersClassNames={{ hasEdition: 'has-edition' }}
              />
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      )}

      {(choice?.kind === 'month' || choice?.kind === 'year') && (
        <select
          aria-label={t(choice.kind === 'month' ? 'filter.pickMonth' : 'filter.pickYear')}
          value={choice.value}
          onChange={(event) => onChange({ kind: choice.kind, value: event.target.value })}
          className="rounded-control border border-ink/10 bg-white px-3.5 py-2 text-[14px] font-semibold outline-none transition-shadow duration-150 hover:border-accent/40 focus-visible:ring-3 focus-visible:ring-accent/20"
        >
          {options[choice.kind].map((value) => (
            <option key={value} value={value}>
              {capitalize(formatPeriod(choice.kind, value, language))}
            </option>
          ))}
        </select>
      )}
    </section>
  )
}
