import { useMutation } from '@tanstack/react-query'
import { CircleCheck, CircleX, FlaskConical, Lock, Save, Trash2, TriangleAlert, X } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { useState, type FormEvent } from 'react'
import { ConfirmDialog } from '../../design/ConfirmDialog'
import { Field, ghostButton, inputClass, primaryButton } from '../../design/Field'
import { Switch } from '../../design/Switch'
import {
  addSource,
  ApiError,
  deleteSource,
  testSource,
  updateSource,
  type SourceConfig,
  type SourceEntry,
  type SourceHealth,
  type SourceTest,
  type SourceValues,
} from '../../lib/api'
import { formatItemTime } from '../../lib/format'
import { useLanguage, type MessageKey } from '../../lib/i18n'
import { HealthBadge } from './SourceBits'
import {
  addableKinds,
  changedValues,
  fieldHintKey,
  fieldLabelKey,
  fieldMeta,
  fieldsWithHint,
  fromForm,
  kindKey,
  optionKey,
  toForm,
  type FormValues,
} from './sourceFields'

export type PanelTarget = { mode: 'add' } | { mode: 'edit'; entry: SourceEntry }

/**
 * Add or edit one source. Writes go through the API, which checks every value
 * again and refuses internal addresses; a test fetches the source without saving.
 */
export function SourcePanel({
  target,
  config,
  health,
  onClose,
  onSaved,
  onConflict,
}: {
  target: PanelTarget
  config: SourceConfig
  health?: SourceHealth
  onClose: () => void
  onSaved: (config: SourceConfig, message: string) => void
  onConflict: () => void
}) {
  const { language, t } = useLanguage()
  const entry = target.mode === 'edit' ? target.entry : null
  const [kind, setKind] = useState<string>(entry?.kind ?? 'rss')
  const [form, setForm] = useState<FormValues>(() => toForm(entry?.values ?? {}))
  const [enabled, setEnabled] = useState(entry?.enabled ?? true)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [conflict, setConflict] = useState(false)
  const [test, setTest] = useState<SourceTest | null>(null)

  const kindInfo = config.kinds.find((candidate) => candidate.id === kind)
  // Adding asks only what identifies the source; details come with their defaults.
  const fields = entry ? Object.keys(entry.values) : (kindInfo?.identity ?? [])
  const locked = entry?.locked ?? false
  const label = entry?.label ?? ''

  const read = () => {
    const { values, errors: problems } = fromForm(fields, form)
    setErrors(Object.fromEntries(Object.entries(problems).map(([name, problem]) => [name, t(problem.key, problem.params)])))
    return Object.keys(problems).length ? null : values
  }

  const failed = (error: Error) => {
    if (error instanceof ApiError && Object.keys(error.fields).length) {
      setErrors(Object.fromEntries(Object.entries(error.fields).map(([name, message]) => [name, t('sources.serverError', { message })])))
    } else if (error instanceof ApiError && error.status === 409) {
      setConflict(true)
    } else {
      setErrors({ _: t('error.save') })
    }
  }

  const save = useMutation({
    mutationFn: (values: SourceValues) => (entry ? updateSource(config.version, entry.key, values) : addSource(config.version, kind, values)),
    onSuccess: (next, values) => {
      const name = entry ? label : String(next.sources.find((source) => source.key === next.key)?.label ?? values.name ?? '')
      onSaved(next, entry ? t('sources.saved') : t('sources.added', { name }))
    },
    onError: failed,
  })
  const remove = useMutation({
    mutationFn: () => deleteSource(config.version, entry!.key),
    onSuccess: (next) => onSaved(next, t('sources.removed', { name: label })),
    onError: failed,
  })
  const run = useMutation({
    mutationFn: (body: Parameters<typeof testSource>[0]) => testSource(body),
    onMutate: () => setTest(null),
    onSuccess: setTest,
    onError: failed,
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setConflict(false)
    const values = locked ? {} : read()
    if (values === null) return
    if (!entry) return save.mutate(values)
    const changed = changedValues(entry, values)
    if (enabled !== entry.enabled) changed.enabled = enabled
    if (Object.keys(changed).length === 0) return onClose()
    save.mutate(changed)
  }

  const runTest = () => {
    setConflict(false)
    // A saved, untouched source is tested by key: its ${VARIABLES} stay on the server.
    if (entry && (locked || Object.keys(changedValues(entry, fromForm(fields, form).values)).length === 0)) {
      return run.mutate({ key: entry.key })
    }
    const values = read()
    if (values !== null) run.mutate({ kind, values })
  }

  const busy = save.isPending || remove.isPending

  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/25 backdrop-blur-sm data-[state=open]:animate-[fade-in_200ms_ease-out]" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 right-0 z-50 flex w-[min(100vw,480px)] flex-col bg-surface shadow-float data-[state=open]:animate-[sheet-in_260ms_var(--ease-soft)] sm:inset-y-3 sm:right-3 sm:rounded-card"
        >
          <header className="flex items-start justify-between gap-4 border-b border-line px-6 pt-6 pb-4">
            <div className="min-w-0">
              <p className="text-[12.5px] font-semibold tracking-wide text-faint uppercase">{entry ? t(kindKey(entry.kind)) : t('sources.panel.add')}</p>
              <Dialog.Title className="mt-0.5 truncate text-[20px] font-bold">{entry ? label : t(kindKey(kind))}</Dialog.Title>
            </div>
            <Dialog.Close
              aria-label={t('sources.panel.close')}
              className="rounded-full p-2 text-ink/60 transition-colors duration-150 hover:bg-canvas hover:text-ink"
            >
              <X size={18} aria-hidden />
            </Dialog.Close>
          </header>

          <form onSubmit={submit} noValidate className="flex min-h-0 flex-1 flex-col">
            <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">
              {!entry && (
                <div>
                  <label htmlFor="source-kind" className="text-[13.5px] font-semibold text-ink/85">
                    {t('sources.panel.kind')}
                  </label>
                  <select
                    id="source-kind"
                    value={kind}
                    onChange={(event) => {
                      setKind(event.target.value)
                      setForm({})
                      setErrors({})
                      setTest(null)
                    }}
                    className={`${inputClass} mt-1.5`}
                  >
                    {addableKinds.map((id) => (
                      <option key={id} value={id}>
                        {t(kindKey(id))}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {entry && health && (
                <div className="rounded-control bg-canvas/70 px-4 py-3 text-[13px] text-muted">
                  <div className="flex flex-wrap items-center gap-2">
                    <HealthBadge status={health.status} />
                    <span>
                      {t('sources.col.lastSuccess')} : {health.last_success_at ? formatItemTime(health.last_success_at, language) : t('sources.never')}
                    </span>
                  </div>
                  {health.last_error && (
                    <p className="mt-2 font-mono text-[12px] break-words text-faint">
                      {t('sources.panel.lastError')} : {health.last_error}
                    </p>
                  )}
                </div>
              )}

              {entry && !entry.group && (
                <div className="flex items-center gap-3">
                  <Switch checked={enabled} onCheckedChange={setEnabled} labelledBy="source-enabled" />
                  <span id="source-enabled" className="text-[14px] text-ink/80">
                    {t('sources.panel.enabled')}
                  </span>
                </div>
              )}

              {locked && (
                <p className="flex gap-2 rounded-control bg-unverified/10 px-4 py-3 text-[13px] leading-relaxed text-unverified">
                  <Lock size={14} aria-hidden className="mt-0.5 shrink-0" />
                  {t('sources.panel.locked')}
                </p>
              )}

              {fields.map((name) => (
                <SourceField
                  key={`${kind}-${name}`}
                  name={name}
                  value={form[name] ?? ''}
                  error={errors[name]}
                  disabled={locked}
                  onChange={(value) => setForm((current) => ({ ...current, [name]: value }))}
                />
              ))}

              <TestBlock running={run.isPending} result={test} onRun={runTest} />
            </div>

            <footer className="flex flex-wrap items-center gap-3 border-t border-line px-6 py-4">
              <p role="status" aria-live="polite" className="w-full text-[13px] font-medium text-rumor empty:hidden">
                {conflict ? t('sources.conflict') : (errors._ ?? '')}
              </p>
              {conflict && (
                <button type="button" onClick={onConflict} className={ghostButton}>
                  {t('sources.reload')}
                </button>
              )}
              {entry?.removable && (
                <ConfirmDialog
                  trigger={
                    <button
                      type="button"
                      disabled={busy}
                      className="flex items-center gap-1.5 rounded-control px-3 py-2.5 text-[14px] font-semibold text-ink/60 transition-colors duration-150 hover:bg-rumor/10 hover:text-rumor"
                    >
                      <Trash2 size={15} aria-hidden />
                      {t('sources.delete')}
                    </button>
                  }
                  title={t('sources.deleteTitle', { name: label })}
                  description={t('sources.deleteBody')}
                  cancel={t('sources.cancel')}
                  confirm={t('sources.delete')}
                  onConfirm={() => remove.mutate()}
                />
              )}
              <div className="ml-auto flex gap-2">
                <Dialog.Close className={ghostButton}>{t('sources.cancel')}</Dialog.Close>
                <button type="submit" disabled={busy} className={primaryButton}>
                  <Save size={15} aria-hidden />
                  {entry ? t('sources.save') : t('sources.create')}
                </button>
              </div>
            </footer>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function SourceField({
  name,
  value,
  error,
  disabled,
  onChange,
}: {
  name: string
  value: string
  error?: string
  disabled: boolean
  onChange: (value: string) => void
}) {
  const { t } = useLanguage()
  const meta = fieldMeta[name] ?? { input: 'text' }
  return (
    <Field label={t(fieldLabelKey(name))} hint={fieldsWithHint.has(name) ? t(fieldHintKey(name)) : undefined} error={error}>
      {(id, describedBy) =>
        meta.input === 'select' ? (
          <select
            id={id}
            value={value}
            disabled={disabled}
            aria-describedby={describedBy}
            onChange={(event) => onChange(event.target.value)}
            className={inputClass}
          >
            {meta.options.map((option) => (
              <option key={option} value={option}>
                {t(optionKey(option))}
              </option>
            ))}
          </select>
        ) : (
          <input
            id={id}
            type={meta.input === 'number' ? 'number' : meta.input === 'url' ? 'url' : 'text'}
            inputMode={meta.input === 'number' ? 'numeric' : undefined}
            min={meta.input === 'number' ? meta.min : undefined}
            max={meta.input === 'number' ? meta.max : undefined}
            value={value}
            disabled={disabled}
            spellCheck={false}
            autoComplete="off"
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            onChange={(event) => onChange(event.target.value)}
            className={`${inputClass} ${meta.input === 'url' || ('mono' in meta && meta.mono) ? 'font-mono text-[13.5px]' : ''}`}
          />
        )
      }
    </Field>
  )
}

export function TestBlock({ running, result, onRun }: { running: boolean; result: SourceTest | null; onRun: () => void }) {
  const { language, t } = useLanguage()
  const tone = !result ? '' : !result.ok ? 'text-rumor' : result.count === 0 ? 'text-unverified' : 'text-confirmed'
  const Icon = !result ? null : !result.ok ? CircleX : result.count === 0 ? TriangleAlert : CircleCheck
  const message: [MessageKey, Record<string, string | number>] | null = !result
    ? null
    : !result.ok
      ? ['sources.test.failed', { error: result.error ?? '' }]
      : result.count === 0
        ? ['sources.test.empty', { days: result.days }]
        : ['sources.test.ok', { count: result.count, days: result.days, inWindow: result.in_window, hours: result.window_hours }]

  return (
    <section aria-labelledby="source-test" className="rounded-control bg-canvas/70 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 id="source-test" className="text-[14px] font-semibold">
            {t('sources.test')}
          </h3>
          <p className="text-[12.5px] text-muted">{t('sources.testHint')}</p>
        </div>
        <button
          type="button"
          onClick={onRun}
          disabled={running}
          className="flex items-center gap-1.5 rounded-full bg-accent-soft px-3.5 py-1.5 text-[13px] font-semibold text-accent transition-all duration-150 ease-soft hover:bg-accent hover:text-on-fill disabled:opacity-60"
        >
          <FlaskConical size={14} aria-hidden className={running ? 'animate-pulse' : ''} />
          {running ? t('sources.testing') : t('sources.test')}
        </button>
      </div>
      <div role="status" aria-live="polite">
        {result && message && Icon && (
          <div className="mt-3">
            <p className={`flex gap-2 text-[13.5px] font-medium ${tone}`}>
              <Icon size={16} aria-hidden className="mt-0.5 shrink-0" />
              <span className="min-w-0 break-words">{t(message[0], message[1])}</span>
            </p>
            {result.warnings.map((warning) => (
              <p key={warning} className="mt-1 text-[12.5px] break-words text-unverified">
                {t('sources.test.warning', { message: warning })}
              </p>
            ))}
            {result.sample.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {result.sample.map((item) => (
                  <li key={item.url} className="text-[13px] leading-snug">
                    <a href={item.url} target="_blank" rel="noreferrer" className="font-medium text-ink hover:text-accent">
                      {item.title}
                    </a>
                    <span className="ml-1.5 text-faint">{formatItemTime(item.published_at, language)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
