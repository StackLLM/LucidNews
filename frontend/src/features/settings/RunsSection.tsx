import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Check, CircleCheck, CircleX, Loader2, Play, TriangleAlert } from 'lucide-react'
import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { inputClass, primaryButton } from '../../design/Field'
import { Switch } from '../../design/Switch'
import {
  ApiError,
  fetchRunCurrent,
  fetchRunHistory,
  fetchSchedule,
  runSteps,
  saveSchedule,
  startRun,
  type HistoryRun,
  type RunCurrent,
  type Schedule,
} from '../../lib/api'
import { capitalize, formatEditionDate, formatItemTime, formatTime } from '../../lib/format'
import { useLanguage, type Language, type MessageKey } from '../../lib/i18n'

const POLL_MS = 2000
const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7] as const

/** Start a run, follow it, schedule it, and see the recent runs (local API only). */
export function RunsSection() {
  const { t } = useLanguage()
  return (
    <section aria-labelledby="runs-title" className="space-y-4">
      <div>
        <h2 id="runs-title" className="text-[20px] font-bold">
          {t('runs.title')}
        </h2>
        <p className="mt-1 text-[14px] text-muted">{t('runs.subtitle')}</p>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <RunCard />
        <ScheduleCard />
      </div>
      <HistoryCard />
    </section>
  )
}

function RunCard() {
  const { language, t } = useLanguage()
  const queryClient = useQueryClient()
  const current = useQuery({
    queryKey: ['run-current'],
    queryFn: ({ signal }) => fetchRunCurrent(signal),
    refetchInterval: (query) => (query.state.data?.running ? POLL_MS : false),
    // Keep following a run while the tab is in the background (only during a run).
    refetchIntervalInBackground: true,
  })
  const [conflict, setConflict] = useState(false)
  const wasRunning = useRef(false)
  const running = current.data?.running ?? false

  // When a run ends: the history, editions and source health have changed.
  useEffect(() => {
    if (wasRunning.current && !running) {
      for (const queryKey of [['run-history'], ['editions'], ['edition'], ['sources'], ['quality-overview'], ['coverage']]) {
        queryClient.invalidateQueries({ queryKey })
      }
    }
    wasRunning.current = running
  }, [running, queryClient])

  const start = useMutation({
    mutationFn: startRun,
    onMutate: () => setConflict(false),
    onSuccess: (data) => queryClient.setQueryData(['run-current'], data),
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) setConflict(true)
      current.refetch()
    },
  })

  const data = current.data
  const logRef = useRef<HTMLPreElement>(null)
  // The last lines matter most (the error, the result): show the end of the log.
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [data?.log])
  return (
    <section aria-labelledby="run-now" className="flex min-w-0 flex-col rounded-card bg-surface p-5 shadow-card sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 id="run-now" className="text-[17px] font-bold">
            {t('runs.start')}
          </h3>
          <p className="mt-1 text-[13px] text-muted">{t('runs.costHint')}</p>
        </div>
        <button type="button" onClick={() => start.mutate()} disabled={running || start.isPending || current.isPending} className={primaryButton}>
          {running || start.isPending ? <Loader2 size={15} aria-hidden className="animate-spin" /> : <Play size={15} aria-hidden />}
          {start.isPending ? t('runs.starting') : t('runs.start')}
        </button>
      </div>

      <div role="status" aria-live="polite" className="mt-4 text-[14px]">
        {conflict && <p className="mb-2 font-medium text-unverified">{t('runs.conflict')}</p>}
        {data && <RunStatus data={data} language={language} />}
      </div>

      {data && (data.running || data.step) && <Steps data={data} />}

      {data?.log && (
        <details open={data.exit_code !== null && data.exit_code !== 0} className="mt-4 rounded-control bg-canvas/70">
          <summary className="cursor-pointer px-3.5 py-2.5 text-[13px] font-semibold text-ink/80">
            {t('runs.log')} <span className="font-normal text-muted">· {t('runs.logHint')}</span>
          </summary>
          <pre
            ref={logRef}
            className="max-h-64 overflow-auto px-3.5 pb-3 font-mono text-[11.5px] leading-relaxed whitespace-pre-wrap text-ink/80 [overflow-wrap:anywhere]"
          >
            {data.log}
          </pre>
        </details>
      )}
    </section>
  )
}

function RunStatus({ data, language }: { data: RunCurrent; language: Language }) {
  const { t } = useLanguage()
  if (data.running) {
    return (
      <p className="flex flex-wrap items-center gap-x-2 font-semibold text-accent">
        <Loader2 size={15} aria-hidden className="animate-spin" />
        {t('runs.running')}
        <span className="font-normal text-muted">
          {data.origin && t(`runs.origin.${data.origin}` as MessageKey)}
          {data.started_at && ` · ${t('runs.since', { time: formatTime(data.started_at, language) })}`}
        </span>
      </p>
    )
  }
  if (data.already_running) return <p className="font-medium text-unverified">{t('runs.alreadyRunning')}</p>
  if (data.exit_code !== null && data.exit_code !== 0) {
    return (
      <p className="flex items-center gap-2 font-medium text-rumor">
        <CircleX size={15} aria-hidden />
        {t('runs.failed', { code: data.exit_code })}
      </p>
    )
  }
  if (data.exit_code === 0 || data.step === 'done') {
    return (
      <p className="flex items-center gap-2 font-medium text-confirmed">
        <CircleCheck size={15} aria-hidden />
        {t('runs.done')}
      </p>
    )
  }
  return <p className="text-muted">{t('runs.idle')}</p>
}

function Steps({ data }: { data: RunCurrent }) {
  const { t } = useLanguage()
  const reached = data.step ? runSteps.indexOf(data.step) : -1
  const failed = !data.running && data.exit_code !== null && data.exit_code !== 0
  return (
    <ol className="mt-4 flex flex-wrap gap-1.5">
      {runSteps.map((step, index) => {
        const done = index < reached || (index === reached && (step === 'done' || (!data.running && !failed)))
        const active = data.running && index === reached
        const tone = active
          ? 'bg-accent text-on-fill'
          : done
            ? 'bg-confirmed/10 text-confirmed'
            : failed && index === reached
              ? 'bg-rumor/10 text-rumor'
              : 'bg-canvas text-faint'
        return (
          <li
            key={step}
            aria-current={active ? 'step' : undefined}
            className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[12.5px] font-semibold ${tone}`}
          >
            {done && <Check size={12} aria-hidden />}
            {t(`runs.step.${step}` as MessageKey)}
          </li>
        )
      })}
    </ol>
  )
}

function ScheduleCard() {
  const { language, t } = useLanguage()
  const queryClient = useQueryClient()
  const id = useId()
  const schedule = useQuery({ queryKey: ['schedule'], queryFn: ({ signal }) => fetchSchedule(signal) })
  const [enabled, setEnabled] = useState(false)
  const [time, setTime] = useState('07:00')
  const [days, setDays] = useState<number[]>([])
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null)

  useEffect(() => {
    const data = schedule.data
    if (!data) return
    setEnabled(data.enabled)
    if (data.hour !== null && data.hour !== undefined && data.minute !== null && data.minute !== undefined) {
      setTime(`${String(data.hour).padStart(2, '0')}:${String(data.minute).padStart(2, '0')}`)
    }
    setDays(data.weekdays ?? [])
  }, [schedule.data])

  const save = useMutation({
    mutationFn: () => {
      if (!enabled) return saveSchedule({ enabled: false })
      const [hour, minute] = time.split(':').map(Number)
      return saveSchedule({ enabled: true, hour, minute, weekdays: days })
    },
    onSuccess: (data: Schedule) => {
      queryClient.setQueryData(['schedule'], data)
      setMessage({ text: data.enabled ? t('schedule.saved') : t('schedule.off') })
    },
    onError: (error) => {
      const detail = error instanceof ApiError ? (error.fields && Object.values(error.fields)[0]) || error.message : ''
      setMessage({ text: t('schedule.refused', { detail: String(detail) }), error: true })
    },
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setMessage(null)
    save.mutate()
  }
  const data = schedule.data

  return (
    <section aria-labelledby={`${id}-title`} className="rounded-card bg-surface p-5 shadow-card sm:p-7">
      <h3 id={`${id}-title`} className="flex items-center gap-2 text-[17px] font-bold">
        <CalendarClock size={17} aria-hidden className="text-accent" />
        {t('schedule.title')}
      </h3>
      <p className="mt-1 text-[13px] leading-relaxed text-muted">{t('schedule.hint')}</p>

      {data && !data.supported ? (
        <p className="mt-4 text-[14px] text-muted">{t('schedule.unsupported')}</p>
      ) : (
        <form onSubmit={submit} className="mt-4 space-y-4">
          <div className="flex items-center gap-3">
            <Switch checked={enabled} onCheckedChange={setEnabled} labelledBy={`${id}-enabled`} disabled={!data} />
            <span id={`${id}-enabled`} className="text-[14px] font-semibold text-ink/85">
              {t('schedule.enabled')}
            </span>
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <label className="w-32 text-[13px] font-semibold text-ink/85">
              {t('schedule.time')}
              <input
                type="time"
                required
                value={time}
                disabled={!enabled}
                onChange={(event) => setTime(event.target.value)}
                className={`${inputClass} mt-1.5`}
              />
            </label>
            <fieldset disabled={!enabled} className="min-w-0">
              <legend className="text-[13px] font-semibold text-ink/85">{t('schedule.days')}</legend>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {WEEKDAYS.map((day) => {
                  const on = days.includes(day)
                  return (
                    <button
                      key={day}
                      type="button"
                      aria-pressed={on}
                      onClick={() => setDays((current) => (on ? current.filter((value) => value !== day) : [...current, day]))}
                      className={`h-9 min-w-11 rounded-full px-2 text-[12.5px] font-semibold transition-colors duration-150 disabled:opacity-50 ${
                        on ? 'bg-ink text-on-fill' : 'bg-canvas text-ink/70 hover:bg-accent-soft'
                      }`}
                    >
                      {t(`schedule.day.${day}` as MessageKey)}
                    </button>
                  )
                })}
              </div>
            </fieldset>
          </div>
          <p className="text-[12.5px] text-muted">{t('schedule.everyDay')}</p>
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={!data || save.isPending || (enabled && !time)} className={primaryButton}>
              {t('schedule.save')}
            </button>
            <p role="status" aria-live="polite" className={`text-[13px] font-medium ${message?.error ? 'text-rumor' : 'text-confirmed'}`}>
              {message?.text ?? ''}
            </p>
          </div>
          {data && (
            <p className="text-[13.5px]">
              {data.valid === false ? (
                <span className="text-rumor">{t('schedule.invalid')}</span>
              ) : data.enabled && data.next_run ? (
                <span className="font-medium">
                  {t('schedule.next', {
                    time: `${capitalize(formatEditionDate(data.next_run, language))}, ${formatTime(data.next_run, language)}`,
                  })}
                </span>
              ) : (
                <span className="text-muted">{t('schedule.none')}</span>
              )}
            </p>
          )}
          {data?.enabled && data.loaded === false && data.valid !== false && (
            <p className="flex gap-2 text-[13px] text-unverified">
              <TriangleAlert size={14} aria-hidden className="mt-0.5 shrink-0" />
              {t('schedule.notLoaded')}
            </p>
          )}
        </form>
      )}
    </section>
  )
}

const KNOWN_STATUSES = ['success', 'empty', 'failed', 'running']
const STATUS_TONES: Record<string, string> = {
  success: 'bg-confirmed/10 text-confirmed ring-confirmed/20',
  empty: 'bg-ink/[0.06] text-ink/60 ring-ink/10',
  failed: 'bg-rumor/10 text-rumor ring-rumor/20',
  running: 'bg-accent-soft text-accent ring-accent/20',
}

function HistoryCard() {
  const { language, t } = useLanguage()
  const history = useQuery({ queryKey: ['run-history'], queryFn: ({ signal }) => fetchRunHistory(signal) })
  const runs = (history.data ?? []).slice(0, 10)
  return (
    <section aria-labelledby="runs-history" className="rounded-card bg-surface p-5 shadow-card sm:p-7">
      <h3 id="runs-history" className="text-[17px] font-bold">
        {t('runs.history')}
      </h3>
      {runs.length === 0 ? (
        <p className="mt-3 text-[14px] text-muted">{history.isPending ? '…' : t('runs.history.none')}</p>
      ) : (
        <ul className="mt-3 divide-y divide-line/70">
          {runs.map((run) => (
            <HistoryRow key={run.id} run={run} language={language} />
          ))}
        </ul>
      )}
    </section>
  )
}

function HistoryRow({ run, language }: { run: HistoryRun; language: Language }) {
  const { t } = useLanguage()
  const statusKey = `runs.status.${run.status}` as MessageKey
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-1.5 py-3 text-[13.5px]">
      <span className="w-40 shrink-0 font-medium tabular-nums">{formatItemTime(run.started_at, language)}</span>
      <span
        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-semibold ring-1 ring-inset ${
          STATUS_TONES[run.status] ?? STATUS_TONES.empty
        }`}
      >
        {KNOWN_STATUSES.includes(run.status) ? t(statusKey) : run.status}
      </span>
      <span className="text-muted tabular-nums">{t('runs.counts', { fetched: run.fetched_count, selected: run.selected_count })}</span>
      {run.ai_limit && <span className="text-[12.5px] text-unverified">{t(`runs.aiLimit.${run.ai_limit}` as MessageKey)}</span>}
      {run.status === 'success' && run.selected_count > 0 && (
        <Link to={`/editions/${run.id}?lang=${language}`} className="ml-auto text-[13px] font-semibold text-accent hover:underline">
          {t('runs.open')}
        </Link>
      )}
      {run.error && (
        <span className="w-full truncate font-mono text-[12px] text-faint" title={run.error}>
          {run.error}
        </span>
      )}
    </li>
  )
}
