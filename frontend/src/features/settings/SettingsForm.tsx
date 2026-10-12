import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, RotateCcw, Save } from 'lucide-react'
import { AnimatePresence, m } from 'motion/react'
import { useEffect, useState, type ReactNode } from 'react'
import { Controller, useForm, type Path } from 'react-hook-form'
import { z } from 'zod'
import { Chip } from '../../design/Chip'
import { errorClass, Field, ghostButton, hintClass, inputClass, labelClass, primaryButton } from '../../design/Field'
import { Switch } from '../../design/Switch'
import { ApiError, reliabilityLabels, saveSettings, type Secret, type Settings, type SettingsValues } from '../../lib/api'
import { labelKey, useLanguage, type MessageKey } from '../../lib/i18n'

const int = (min: number, max: number) =>
  z
    .number({ error: 'settings.errNumber' })
    .int({ error: 'settings.errNumber' })
    .min(min, { error: 'settings.errNumber' })
    .max(max, { error: 'settings.errNumber' })

// Mirrors the server rules (lucidnews/models.py); the server checks again on save.
const schema = z.object({
  ai: z.object({
    enabled: z.boolean(),
    provider: z.string(),
    model: z.string().trim().min(1, { error: 'settings.errRequired' }),
    api_key_env: z.string().regex(/^[A-Za-z_][A-Za-z0-9_]{0,99}$/, { error: 'settings.errVariable' }),
    languages: z.array(z.string()).min(1, { error: 'settings.errLanguages' }),
    max_requests_per_minute: int(1, 10_000).nullable(),
    max_tokens_per_run: int(1, 100_000_000).nullable(),
  }),
  collection: z.object({ time_window_hours: int(1, 720) }),
  digest: z.object({
    max_items: int(1, 500).nullable(),
    unanalyzed_max_items: int(0, 500),
    source_quality_days: int(0, 365),
  }),
  reliability: z.object({
    exclude_labels: z.array(z.enum(reliabilityLabels)),
    corroboration_lookback_hours: int(0, 720),
    corroboration_max_references: int(0, 500),
  }),
  archive: z.object({ reuse_analysis: z.boolean(), reuse_enrichment: z.boolean() }),
  profiles: z.record(
    z.string(),
    z.object({
      threshold: z.number({ error: 'settings.errScore' }).min(0, { error: 'settings.errScore' }).max(10, { error: 'settings.errScore' }).nullable(),
      topic_dedup: z.boolean(),
    }),
  ),
})

const asNumber = (value: unknown) => (value === '' || value === null || value === undefined ? null : Number(value))

export function SettingsForm({ settings, secrets, onConflict }: { settings: Settings; secrets: Secret[] | undefined; onConflict: () => void }) {
  const { language, t } = useLanguage()
  const queryClient = useQueryClient()
  const [saved, setSaved] = useState(false)
  const [conflict, setConflict] = useState(false)
  const form = useForm<SettingsValues>({ resolver: zodResolver(schema), defaultValues: settings.values })
  const { errors, isDirty } = form.formState
  const locked = new Set(settings.locked)
  const { options } = settings

  // A new version (our save, a restore, a reload after a conflict): show its values.
  useEffect(() => {
    form.reset(settings.values)
    setConflict(false)
  }, [settings.version]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!saved) return
    const timer = window.setTimeout(() => setSaved(false), 3000)
    return () => window.clearTimeout(timer)
  }, [saved])

  const save = useMutation({
    mutationFn: (values: SettingsValues) => saveSettings(settings.version, values),
    onSuccess: (updated) => {
      queryClient.setQueryData(['settings'], updated)
      void queryClient.invalidateQueries({ queryKey: ['settings-backups'] })
      void queryClient.invalidateQueries({ queryKey: ['secrets'] }) // the key variable may have changed
      setSaved(true)
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setConflict(true)
        return
      }
      const fields = error instanceof ApiError ? Object.entries(error.fields) : []
      if (fields.length === 0) form.setError('root', { message: t('error.save') })
      for (const [field, message] of fields) {
        form.setError(field as Path<SettingsValues>, { message: t('error.server', { message }) })
      }
    },
  })

  const message = (path: string): string | undefined => {
    const error = path.split('.').reduce<unknown>((node, key) => (node as Record<string, unknown> | undefined)?.[key], errors) as
      { message?: string } | undefined
    if (!error?.message) return undefined
    return error.message.startsWith('settings.') ? t(error.message as MessageKey) : error.message
  }
  const numberField = (name: Path<SettingsValues>, label: MessageKey, hint?: MessageKey, step = 1) => (
    <Field label={t(label)} hint={hint && t(hint)} error={message(name)} locked={locked.has(name)}>
      {(id, describedBy) => (
        <input
          id={id}
          type="number"
          inputMode="numeric"
          step={step}
          disabled={locked.has(name)}
          aria-describedby={describedBy}
          {...form.register(name, { setValueAs: asNumber })}
          className={inputClass}
        />
      )}
    </Field>
  )
  const toggleIn = (name: 'ai.languages' | 'reliability.exclude_labels', value: string) => {
    const current = form.getValues(name) as string[]
    form.setValue(name, (current.includes(value) ? current.filter((entry) => entry !== value) : [...current, value]) as never, {
      shouldDirty: true,
      shouldValidate: true,
    })
  }
  const aiEnabled = form.watch('ai.enabled')
  const savedKey = secrets?.find((secret) => secret.name === settings.values.ai.api_key_env)
  const languagesValue = form.watch('ai.languages')
  const excludedValue = form.watch('reliability.exclude_labels')

  return (
    <form onSubmit={form.handleSubmit((values) => save.mutate(values))} className="space-y-6" noValidate>
      <Section title={t('settings.ai')}>
        <div className="sm:col-span-2">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              disabled={locked.has('ai.enabled')}
              aria-describedby="ai-enable-hint"
              {...form.register('ai.enabled')}
              className="mt-0.5 h-5 w-5 shrink-0 cursor-pointer rounded-md accent-accent"
            />
            <span className="text-[14.5px] font-semibold">{t('settings.aiEnable')}</span>
          </label>
          <p id="ai-enable-hint" className={`${hintClass} ml-8`}>
            {t('settings.aiEnableHint')}
          </p>
        </div>
        {aiEnabled && (
          <div className="space-y-3 rounded-control bg-canvas/70 p-4 sm:col-span-2">
            <p className="text-[13.5px] leading-relaxed text-muted">{t('settings.aiKeyWhere')}</p>
            {savedKey && (
              <p className="flex items-center gap-2 text-[13.5px] font-semibold">
                <span aria-hidden className={`h-2 w-2 rounded-full ${savedKey.in_file || savedKey.in_environment ? 'bg-confirmed' : 'bg-unverified'}`} />
                <span>
                  {t('settings.aiKey', { name: savedKey.name })} ·{' '}
                  {t(savedKey.in_file || savedKey.in_environment ? 'settings.aiKeyFound' : 'settings.aiKeyMissing')}
                </span>
              </p>
            )}
          </div>
        )}
        {aiEnabled && (
          <>
            <Field label={t('settings.provider')} locked={locked.has('ai.provider')}>
              {(id) => (
                <select
                  id={id}
                  disabled={locked.has('ai.provider')}
                  {...form.register('ai.provider', {
                    onChange: (event) => {
                      // A new provider starts from its usual model and key variable.
                      const provider = options.providers.find((entry) => entry.id === event.target.value)
                      if (!provider) return
                      if (!locked.has('ai.model')) form.setValue('ai.model', provider.model, { shouldDirty: true, shouldValidate: true })
                      if (!locked.has('ai.api_key_env') && provider.api_key_env)
                        form.setValue('ai.api_key_env', provider.api_key_env, { shouldDirty: true, shouldValidate: true })
                    },
                  })}
                  className={inputClass}
                >
                  {options.providers.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.id}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label={t('settings.model')} error={message('ai.model')} locked={locked.has('ai.model')}>
              {(id) => <input id={id} disabled={locked.has('ai.model')} {...form.register('ai.model')} className={inputClass} />}
            </Field>
            <Field label={t('settings.apiKeyEnv')} hint={t('settings.apiKeyEnvHint')} error={message('ai.api_key_env')} locked={locked.has('ai.api_key_env')}>
              {(id, describedBy) => (
                <input
                  id={id}
                  spellCheck={false}
                  autoComplete="off"
                  disabled={locked.has('ai.api_key_env')}
                  aria-describedby={describedBy}
                  {...form.register('ai.api_key_env')}
                  className={`${inputClass} font-mono`}
                />
              )}
            </Field>
            {numberField('ai.max_requests_per_minute', 'settings.rpm', 'settings.rpmHint')}
            {numberField('ai.max_tokens_per_run', 'settings.budget', 'settings.budgetHint', 1000)}
          </>
        )}
        <fieldset className="sm:col-span-2">
          <legend className={labelClass}>{t('settings.languages')}</legend>
          <p className={hintClass}>{t('settings.languagesHint')}</p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {options.languages.map((entry) => (
              <Chip key={entry.code} selected={languagesValue.includes(entry.code)} onToggle={() => toggleIn('ai.languages', entry.code)}>
                {entry.name}
              </Chip>
            ))}
          </div>
          {message('ai.languages') && <p className={errorClass}>{message('ai.languages')}</p>}
        </fieldset>
      </Section>

      <Section title={t('settings.collection')}>{numberField('collection.time_window_hours', 'settings.window', 'settings.windowHint')}</Section>

      <Section title={t('settings.selection')}>
        <div className="space-y-3 sm:col-span-2">
          {options.profiles.map((profile) => {
            const name = profile.names[language] ?? profile.names.default ?? profile.id
            const threshold = `profiles.${profile.id}.threshold` as Path<SettingsValues>
            const dedup = `profiles.${profile.id}.topic_dedup` as Path<SettingsValues>
            const dedupLabel = `${profile.id}-dedup`
            return (
              <div key={profile.id} className="grid gap-3 rounded-control bg-canvas/70 p-4 sm:grid-cols-[1fr_160px] sm:items-start">
                <div>
                  <p className="font-semibold">{name}</p>
                  <div className="mt-2.5 flex items-center gap-3">
                    <Controller
                      control={form.control}
                      name={dedup}
                      render={({ field }) => <Switch checked={Boolean(field.value)} onCheckedChange={field.onChange} labelledBy={dedupLabel} />}
                    />
                    <span id={dedupLabel} className="text-[13.5px] text-ink/75">
                      {t('settings.dedup')}
                    </span>
                  </div>
                </div>
                <Field label={t('settings.threshold')} hint={t('settings.thresholdHint')} error={message(threshold)}>
                  {(id, describedBy) => (
                    <input
                      id={id}
                      type="number"
                      step={0.5}
                      inputMode="decimal"
                      aria-describedby={describedBy}
                      {...form.register(threshold, { setValueAs: asNumber })}
                      className={inputClass}
                    />
                  )}
                </Field>
              </div>
            )
          })}
        </div>
        {numberField('digest.max_items', 'settings.maxItems', 'settings.maxItemsHint')}
        {numberField('digest.unanalyzed_max_items', 'settings.unanalyzed', 'settings.unanalyzedHint')}
      </Section>

      <Section title={t('settings.reliability')}>
        <fieldset className="sm:col-span-2">
          <legend className={labelClass}>{t('settings.exclude')}</legend>
          <p className={hintClass}>{t('settings.excludeHint')}</p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {options.labels.map((label) => (
              <Chip key={label} selected={excludedValue.includes(label)} onToggle={() => toggleIn('reliability.exclude_labels', label)}>
                {t(labelKey(label))}
              </Chip>
            ))}
          </div>
        </fieldset>
        {numberField('reliability.corroboration_lookback_hours', 'settings.lookback')}
        {numberField('reliability.corroboration_max_references', 'settings.references', 'settings.referencesHint')}
      </Section>

      <Section title={t('settings.archive')}>
        {(['archive.reuse_analysis', 'archive.reuse_enrichment'] as const).map((name) => (
          <div key={name} className="flex items-center gap-3 sm:col-span-2">
            <Controller
              control={form.control}
              name={name}
              render={({ field }) => <Switch checked={field.value} onCheckedChange={field.onChange} labelledBy={`${name}-label`} />}
            />
            <span id={`${name}-label`} className="text-[14px] text-ink/80">
              {t(name === 'archive.reuse_analysis' ? 'settings.reuseAnalysis' : 'settings.reuseEnrichment')}
            </span>
          </div>
        ))}
        {numberField('digest.source_quality_days', 'settings.qualityDays', 'settings.qualityDaysHint')}
      </Section>

      {/* Floating save bar: visible while something is unsaved or just saved. */}
      <AnimatePresence>
        {(isDirty || saved || conflict || errors.root) && (
          <m.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            className="glass sticky bottom-24 z-20 flex flex-wrap items-center gap-3 rounded-card px-5 py-3.5 lg:bottom-6"
          >
            <p role="status" aria-live="polite" className="min-w-0 flex-1 text-[13.5px] font-medium">
              {conflict ? (
                <span className="text-rumor">{t('settings.conflict')}</span>
              ) : errors.root ? (
                <span className="text-rumor">{errors.root.message}</span>
              ) : saved && !isDirty ? (
                <span className="flex items-center gap-1.5 text-confirmed">
                  <Check size={15} aria-hidden />
                  {t('settings.saved')}
                </span>
              ) : (
                t('settings.unsaved')
              )}
            </p>
            {conflict ? (
              <button type="button" onClick={onConflict} className={primaryButton}>
                <RotateCcw size={15} aria-hidden />
                {t('settings.reload')}
              </button>
            ) : (
              isDirty && (
                <>
                  <button type="button" onClick={() => form.reset(settings.values)} className={ghostButton}>
                    {t('settings.discard')}
                  </button>
                  <button type="submit" disabled={save.isPending} className={primaryButton}>
                    <Save size={15} aria-hidden />
                    {t('settings.save')}
                  </button>
                </>
              )
            )}
          </m.div>
        )}
      </AnimatePresence>
    </form>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-card bg-surface p-5 shadow-card sm:p-7">
      <h2 className="text-[17px] font-bold">{title}</h2>
      <div className="mt-5 grid gap-5 sm:grid-cols-2">{children}</div>
    </section>
  )
}
