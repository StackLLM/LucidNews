import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, Crown, Save, Trash2, Undo2 } from 'lucide-react'
import { AnimatePresence, m } from 'motion/react'
import { useEffect, useState, type ReactNode } from 'react'
import { useForm, type Path } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { z } from 'zod'
import { Chip } from '../../design/Chip'
import { ConfirmDialog } from '../../design/ConfirmDialog'
import { Segmented } from '../../design/PageState'
import { Switch } from '../../design/Switch'
import { ApiError, deleteSubscriber, preferencesSchema, updatePreferences, type PreferenceOptions, type Preferences, type Subscriber } from '../../lib/api'
import { formatEditionDate, sourceName } from '../../lib/format'
import { categoryLabel, useLanguage, type MessageKey } from '../../lib/i18n'
import { expand } from '../../lib/motion'

const formSchema = preferencesSchema.extend({
  max_items: z.number({ error: 'maxItems' }).int({ error: 'maxItems' }).min(1, { error: 'maxItems' }).max(100, { error: 'maxItems' }).nullable(),
})

// 2024-01-01 was a Monday: day 0 of the API's week (0 = Monday).
const weekdayName = (day: number, language: string) => new Date(Date.UTC(2024, 0, 1 + day)).toLocaleDateString(language, { weekday: 'long', timeZone: 'UTC' })

type ImportanceChoice = 'all' | 'medium' | 'high' | 'critical'

export function PreferencesForm({ subscriber, options }: { subscriber: Subscriber; options: PreferenceOptions }) {
  const { language, t } = useLanguage()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [saved, setSaved] = useState(false)
  const form = useForm<Preferences>({ resolver: zodResolver(formSchema), defaultValues: subscriber.preferences })
  const values = form.watch()
  const { isDirty, errors } = form.formState

  useEffect(() => {
    if (!saved) return
    const timer = window.setTimeout(() => setSaved(false), 2500)
    return () => window.clearTimeout(timer)
  }, [saved])

  const set = <K extends keyof Preferences>(name: K, value: Preferences[K]) =>
    form.setValue(name as Path<Preferences>, value as never, { shouldDirty: true, shouldValidate: true })
  // Read the live value, not the render snapshot: two quick clicks must both count.
  const toggle = (name: 'categories' | 'sources', value: string) => {
    const current = form.getValues(name)
    set(name, current.includes(value) ? current.filter((entry) => entry !== value) : [...current, value])
  }

  const save = useMutation({
    mutationFn: (preferences: Preferences) => updatePreferences(subscriber.id, preferences),
    onSuccess: (updated) => {
      queryClient.setQueryData<Subscriber[]>(['subscribers'], (list) => list?.map((entry) => (entry.id === updated.id ? updated : entry)))
      form.reset(updated.preferences)
      setSaved(true)
    },
    onError: (error) => {
      const fields = error instanceof ApiError ? Object.entries(error.fields) : []
      if (fields.length === 0) {
        form.setError('root', { message: t('error.save') })
        return
      }
      for (const [field, message] of fields) {
        const name = (field.split('.')[0] in values ? field.split('.')[0] : 'root') as Path<Preferences> | 'root'
        form.setError(name, { message: t('error.server', { message }) })
      }
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteSubscriber(subscriber.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['subscribers'] })
      navigate({ pathname: '/preferences', search: `?lang=${language}` })
    },
    onError: () => form.setError('root', { message: t('error.save') }),
  })

  const sourceTypes = options.sources.filter((option) => option.kind === 'type')
  const namedSources = options.sources.filter((option) => option.kind === 'source')
  const [showNamed, setShowNamed] = useState(() => namedSources.some((option) => values.sources.includes(option.value)))
  const importance: ImportanceChoice = values.min_importance === null || values.min_importance === 'low' ? 'all' : values.min_importance
  const errorText = (message?: string) => (message === 'maxItems' ? t('error.maxItems') : message)

  return (
    <form
      noValidate
      onSubmit={form.handleSubmit((preferences) => save.mutate(preferences))}
      className="relative rounded-card bg-surface shadow-card"
      aria-labelledby="subscriber-email"
    >
      <header className="flex flex-wrap items-center gap-4 border-b border-line p-5 sm:p-7">
        <span aria-hidden className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-accent-soft text-[18px] font-bold uppercase text-accent">
          {subscriber.email.charAt(0)}
        </span>
        <div className="min-w-0 flex-1">
          <h2 id="subscriber-email" className="truncate text-[17px] font-bold">
            {subscriber.email}
          </h2>
          <p className="text-[13px] text-muted">{t('prefs.since', { date: formatEditionDate(subscriber.created_at, language) })}</p>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-canvas px-3 py-1 text-[12.5px] font-semibold text-ink/70">
          {subscriber.plan === 'premium' && <Crown size={13} className="text-unverified" aria-hidden />}
          {t(`prefs.plan.${subscriber.plan}` as MessageKey)}
        </span>
        <ConfirmDialog
          title={t('prefs.deleteTitle')}
          description={t('prefs.deleteBody', { email: subscriber.email })}
          cancel={t('prefs.cancel')}
          confirm={t('prefs.deleteConfirm')}
          onConfirm={() => remove.mutate()}
          trigger={
            <button
              type="button"
              className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold text-rumor transition-colors duration-150 hover:bg-rumor/[0.08]"
            >
              <Trash2 size={15} aria-hidden />
              {t('prefs.delete')}
            </button>
          }
        />
      </header>

      <div className="divide-y divide-line">
        <Field title={t('prefs.language')}>
          <Segmented
            id="pref-language"
            label={t('prefs.language')}
            value={values.language}
            onChange={(value) => set('language', value)}
            options={options.languages.map((entry) => ({ value: entry.code, label: entry.name }))}
          />
        </Field>

        <Field title={t('prefs.categories')} hint={t('prefs.categoriesHint')} count={values.categories.length}>
          <div className="flex flex-wrap gap-2">
            {options.categories.map((category) => (
              <Chip key={category} selected={values.categories.includes(category)} onToggle={() => toggle('categories', category)}>
                {categoryLabel(language, category)}
              </Chip>
            ))}
          </div>
          <FieldError message={errors.categories?.message} />
        </Field>

        <Field title={t('prefs.sources')} hint={t('prefs.sourcesHint')} count={values.sources.length}>
          <div className="flex flex-wrap gap-2">
            {sourceTypes.map((option) => (
              <Chip key={option.value} selected={values.sources.includes(option.value)} onToggle={() => toggle('sources', option.value)}>
                {t('prefs.sourcesAll', { type: sourceName(option.value) })}
              </Chip>
            ))}
          </div>
          {namedSources.length > 0 && (
            <>
              <button
                type="button"
                aria-expanded={showNamed}
                onClick={() => setShowNamed((open) => !open)}
                className="mt-4 flex items-center gap-1.5 text-[13px] font-semibold text-accent"
              >
                {showNamed ? t('prefs.hideSources') : t('prefs.showSources', { count: namedSources.length })}
                <ChevronDown size={14} aria-hidden className={`transition-transform duration-200 ease-soft ${showNamed ? 'rotate-180' : ''}`} />
              </button>
              <AnimatePresence initial={false}>
                {showNamed && (
                  <m.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={expand}
                    className="overflow-hidden"
                  >
                    <div className="flex flex-wrap gap-2 pt-3">
                      {namedSources.map((option) => (
                        <Chip
                          key={`${option.type}/${option.value}`}
                          selected={values.sources.includes(option.value)}
                          onToggle={() => toggle('sources', option.value)}
                        >
                          {option.value}
                          <span className="text-[11px] opacity-60">{sourceName(option.type)}</span>
                        </Chip>
                      ))}
                    </div>
                  </m.div>
                )}
              </AnimatePresence>
            </>
          )}
          <FieldError message={errors.sources?.message} />
        </Field>

        <Field title={t('prefs.frequency')}>
          <Segmented
            id="pref-frequency"
            label={t('prefs.frequency')}
            value={values.frequency}
            onChange={(value) => set('frequency', value)}
            options={options.frequencies.map((frequency) => ({ value: frequency, label: t(`freq.${frequency}` as MessageKey) }))}
          />
          {values.frequency === 'weekly' && (
            <p className="mt-2.5 text-[13px] text-muted">{t('prefs.weeklyHint', { day: weekdayName(options.weekly_day, language) })}</p>
          )}
        </Field>

        <Field title={t('prefs.detail')} hint={t(`prefs.detailHint.${values.detail_level}` as MessageKey)}>
          <Segmented
            id="pref-detail"
            label={t('prefs.detail')}
            value={values.detail_level}
            onChange={(value) => set('detail_level', value)}
            options={options.detail_levels.map((level) => ({ value: level, label: t(`prefs.detail.${level}` as MessageKey) }))}
          />
        </Field>

        <Field title={t('prefs.importance')}>
          <Segmented<ImportanceChoice>
            id="pref-importance"
            label={t('prefs.importance')}
            value={importance}
            onChange={(value) => set('min_importance', value === 'all' ? null : value)}
            options={[
              { value: 'all', label: t('prefs.importanceAll') },
              { value: 'medium', label: t('prefs.importanceMedium') },
              { value: 'high', label: t('prefs.importanceHigh') },
              { value: 'critical', label: t('prefs.importanceCritical') },
            ]}
          />
        </Field>

        <div className="flex items-start justify-between gap-6 p-5 sm:p-7">
          <div>
            <p id="pref-unconfirmed" className="text-[15px] font-semibold">
              {t('prefs.unconfirmed')}
            </p>
            <p id="pref-unconfirmed-hint" className="mt-1 text-[13px] text-muted">
              {t('prefs.unconfirmedHint')}
            </p>
          </div>
          <Switch
            checked={values.include_unconfirmed}
            onCheckedChange={(checked) => set('include_unconfirmed', checked)}
            labelledBy="pref-unconfirmed"
            describedBy="pref-unconfirmed-hint"
          />
        </div>

        <Field title={t('prefs.maxItems')} htmlFor="pref-max-items">
          <input
            id="pref-max-items"
            type="number"
            inputMode="numeric"
            min={1}
            max={100}
            placeholder={t('prefs.maxItemsPlaceholder')}
            aria-invalid={!!errors.max_items}
            {...form.register('max_items', { setValueAs: (value) => (value === '' || value === null ? null : Number(value)) })}
            className="w-40 rounded-control border border-ink/10 bg-surface px-3.5 py-2.5 text-[14px] outline-none transition-shadow duration-150 placeholder:text-faint focus:border-accent/50 focus:ring-3 focus:ring-accent/15 aria-invalid:border-rumor/50"
          />
          <FieldError message={errorText(errors.max_items?.message)} />
        </Field>
      </div>

      <FieldError message={errors.root?.message} className="px-7 pb-4" />

      {/* Save bar: appears only with unsaved changes, stays in reach while scrolling. */}
      <div className="sticky bottom-24 z-10 px-4 pb-4 md:bottom-4">
        <AnimatePresence>
          {(isDirty || saved) && (
            <m.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 12 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="glass flex flex-wrap items-center gap-3 rounded-[18px] px-4 py-3"
            >
              <p role="status" aria-live="polite" className="flex items-center gap-2 text-[14px] font-medium">
                {saved && !isDirty ? (
                  <>
                    <Check size={16} className="text-confirmed" aria-hidden />
                    {t('prefs.saved')}
                  </>
                ) : (
                  t('prefs.dirty')
                )}
              </p>
              {isDirty && (
                <span className="ml-auto flex gap-2">
                  <button
                    type="button"
                    onClick={() => form.reset()}
                    className="flex items-center gap-1.5 rounded-control px-3.5 py-2.5 text-[14px] font-semibold text-ink/70 transition-colors duration-150 hover:bg-surface"
                  >
                    <Undo2 size={15} aria-hidden />
                    {t('prefs.cancel')}
                  </button>
                  <button
                    type="submit"
                    disabled={save.isPending}
                    className="flex items-center gap-1.5 rounded-control bg-accent px-5 py-2.5 text-[14px] font-semibold text-on-fill shadow-accent transition-all duration-150 ease-soft hover:-translate-y-0.5 hover:bg-accent-deep active:translate-y-0 disabled:opacity-60"
                  >
                    <Save size={15} aria-hidden />
                    {t('prefs.save')}
                  </button>
                </span>
              )}
            </m.div>
          )}
        </AnimatePresence>
      </div>
    </form>
  )
}

function Field({ title, hint, count, htmlFor, children }: { title: string; hint?: string; count?: number; htmlFor?: string; children: ReactNode }) {
  const Title = htmlFor ? 'label' : 'p'
  return (
    <div className="p-5 sm:p-7">
      <div className="mb-3.5 flex items-baseline justify-between gap-4">
        <Title {...(htmlFor ? { htmlFor } : {})} className="text-[15px] font-semibold">
          {title}
          {count ? <span className="ml-2 rounded-full bg-accent-soft px-2 py-0.5 text-[12px] text-accent tabular-nums">{count}</span> : null}
        </Title>
        {hint && <p className="text-right text-[12.5px] text-muted">{hint}</p>}
      </div>
      {children}
    </div>
  )
}

function FieldError({ message, className = '' }: { message?: string; className?: string }) {
  if (!message) return null
  return (
    <p role="alert" className={`mt-2 text-[13px] text-rumor ${className}`}>
      {message}
    </p>
  )
}
