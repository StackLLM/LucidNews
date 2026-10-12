import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, ArrowUpRight, Check, CircleCheck, Eraser, EyeOff, MessageSquare } from 'lucide-react'
import { AnimatePresence, m } from 'motion/react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router'
import { Chip } from '../../design/Chip'
import { ApiErrorCard, PageSkeleton, Segmented } from '../../design/PageState'
import {
  claimStatuses,
  deleteAnnotation,
  fetchEvalItems,
  importanceLevels,
  saveAnnotation,
  type AnnotationInput,
  type ClaimStatus,
  type EvalItem,
} from '../../lib/api'
import { formatItemTime, sourceName } from '../../lib/format'
import { categoryLabel, useLanguage, type MessageKey } from '../../lib/i18n'
import { categories } from './categories'

type Draft = Partial<AnnotationInput> & { categories: string[]; notes: string }

const emptyDraft = (): Draft => ({ categories: [], notes: '' })
const MAX_CATEGORIES = 3

export function AnnotateView() {
  const query = useQuery({ queryKey: ['eval-items'], queryFn: ({ signal }) => fetchEvalItems(signal) })
  if (query.isPending) return <PageSkeleton blocks={2} />
  if (query.isError) return <ApiErrorCard error={query.error} onRetry={() => query.refetch()} />
  return <Annotator items={query.data.items} />
}

function Annotator({ items }: { items: EvalItem[] }) {
  const { t } = useLanguage()
  const [params, setParams] = useSearchParams()
  const [filter, setFilter] = useState<'todo' | 'all'>('todo')
  const done = items.filter((item) => item.annotation).length
  const visible = filter === 'todo' ? items.filter((item) => !item.annotation) : items
  const requested = items.find((item) => item.id === params.get('item'))
  const current = requested ?? visible[0]

  const select = (id: string) =>
    setParams(
      (next) => {
        next.set('item', id)
        return next
      },
      { replace: true },
    )

  if (items.length === 0) return <EmptyCard text={t('quality.noItems')} />

  return (
    <div className="space-y-6">
      <section aria-label={t('quality.progress', { done, total: items.length })} className="glass rounded-card p-5 sm:px-7">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-[15px] font-semibold">{t('quality.progress', { done, total: items.length })}</p>
            <span className="mt-2.5 block h-2 overflow-hidden rounded-full bg-accent-soft" aria-hidden>
              <m.span
                className="block h-full rounded-full bg-accent"
                initial={false}
                animate={{ width: `${(done / items.length) * 100}%` }}
                transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              />
            </span>
            <p className="mt-2 text-[12.5px] text-muted">{t('quality.target')}</p>
          </div>
          <Segmented
            id="quality-filter"
            label={t('quality.todo')}
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'todo', label: `${t('quality.todo')} · ${items.length - done}` },
              { value: 'all', label: `${t('quality.all')} · ${items.length}` },
            ]}
          />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)] lg:gap-8">
        <nav aria-label={t('quality.todo')} className="glass self-start rounded-card p-3 lg:sticky lg:top-28">
          {visible.length === 0 ? (
            <p className="p-3 text-[13.5px] text-muted">{t('quality.allDone')}</p>
          ) : (
            <ul className="max-h-[60vh] space-y-1 overflow-y-auto">
              {visible.map((item) => {
                const active = item.id === current?.id
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => select(item.id)}
                      aria-current={active ? 'true' : undefined}
                      className={`flex w-full items-start gap-2.5 rounded-control px-3 py-2.5 text-left transition-all duration-150 ${
                        active ? 'bg-surface shadow-card ring-1 ring-accent/25' : 'hover:bg-surface/70'
                      }`}
                    >
                      {item.annotation ? (
                        <CircleCheck size={16} className="mt-0.5 shrink-0 text-confirmed" aria-label={t('quality.annotated')} />
                      ) : (
                        <span aria-hidden className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent/40" />
                      )}
                      <span className="line-clamp-2 text-[13.5px] leading-snug font-medium">{item.title}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </nav>

        {current ? (
          <AnnotationCard
            key={current.id}
            item={current}
            onDone={() => {
              const next = items.find((item) => !item.annotation && item.id !== current.id)
              if (next) select(next.id)
            }}
          />
        ) : (
          <EmptyCard text={t('quality.allDone')} />
        )}
      </div>
    </div>
  )
}

function AnnotationCard({ item, onDone }: { item: EvalItem; onDone: () => void }) {
  const { language, t } = useLanguage()
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Draft>(() => (item.annotation ? { ...item.annotation } : emptyDraft()))
  const [missing, setMissing] = useState(false)
  const [saved, setSaved] = useState(false)
  const complete = draft.relevant !== undefined && draft.importance !== undefined && draft.claim_status !== undefined

  useEffect(() => {
    if (!saved) return
    const timer = window.setTimeout(() => setSaved(false), 2000)
    return () => window.clearTimeout(timer)
  }, [saved])

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['eval-items'] })
  const save = useMutation({
    mutationFn: (next: boolean) =>
      saveAnnotation(item.id, {
        relevant: draft.relevant!,
        importance: draft.importance!,
        claim_status: draft.claim_status!,
        categories: draft.categories,
        notes: draft.notes.trim(),
      }).then(() => next),
    onSuccess: async (next) => {
      queryClient.removeQueries({ queryKey: ['quality-report'] })
      await refresh()
      setSaved(true)
      if (next) onDone()
    },
  })
  const clear = useMutation({
    mutationFn: () => deleteAnnotation(item.id),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: ['quality-report'] })
      setDraft(emptyDraft())
      await refresh()
    },
  })

  const submit = (next: boolean) => {
    if (!complete) {
      setMissing(true)
      return
    }
    setMissing(false)
    save.mutate(next)
  }
  const toggleCategory = (category: string) =>
    setDraft((current) => ({
      ...current,
      categories: current.categories.includes(category)
        ? current.categories.filter((entry) => entry !== category)
        : current.categories.length >= MAX_CATEGORIES
          ? current.categories
          : [...current.categories, category],
    }))
  const claimOptions = useMemo(() => claimStatuses.map((status) => ({ status, label: t(`claim.${status}` as MessageKey) })), [t])

  return (
    <article aria-labelledby="annotate-title" className="min-w-0 rounded-card bg-surface shadow-card">
      <header className="border-b border-line p-5 sm:p-8">
        <p className="text-[13px] text-muted">
          <span className="font-semibold text-ink/70">{item.source}</span> · {sourceName(item.source_type)} ·{' '}
          <time dateTime={item.published_at}>{formatItemTime(item.published_at, language)}</time>
        </p>
        <h2 id="annotate-title" className="mt-2 font-serif text-[26px] leading-[1.2] font-medium sm:text-[30px]">
          {item.title}
        </h2>
        {item.excerpt && <p className="mt-3 font-serif text-[16.5px] leading-[1.65] text-ink/75">{item.excerpt}</p>}
        <div className="mt-4 flex flex-wrap items-center gap-4 text-[13.5px] font-semibold">
          <a href={item.url} target="_blank" rel="noreferrer noopener" className="flex items-center gap-1 text-accent hover:text-accent-deep">
            {t('quality.open')}
            <ArrowUpRight size={14} aria-hidden />
          </a>
          {item.discussion_url && (
            <a href={item.discussion_url} target="_blank" rel="noreferrer noopener" className="flex items-center gap-1.5 text-muted hover:text-ink">
              <MessageSquare size={14} aria-hidden />
              {t('quality.discussion')}
            </a>
          )}
        </div>
        <p className="mt-5 flex items-center gap-2 rounded-control bg-accent-soft/70 px-3.5 py-2.5 text-[13px] text-accent">
          <EyeOff size={15} aria-hidden />
          {t('quality.blind')}
        </p>
      </header>

      <div className="space-y-7 p-5 sm:p-8">
        <Question title={t('quality.qRelevant')}>
          <Segmented<'yes' | 'no' | ''>
            id={`relevant-${item.id}`}
            label={t('quality.qRelevant')}
            value={draft.relevant === undefined ? '' : draft.relevant ? 'yes' : 'no'}
            onChange={(value) => setDraft((current) => ({ ...current, relevant: value === 'yes' }))}
            options={[
              { value: 'yes', label: t('quality.yes') },
              { value: 'no', label: t('quality.no') },
            ]}
          />
        </Question>

        <Question title={t('quality.qImportance')}>
          <Segmented<string>
            id={`importance-${item.id}`}
            label={t('quality.qImportance')}
            value={draft.importance ?? ''}
            onChange={(value) => setDraft((current) => ({ ...current, importance: value as AnnotationInput['importance'] }))}
            options={importanceLevels.map((level) => ({ value: level, label: t(`importance.${level}` as MessageKey) }))}
          />
        </Question>

        <Question title={t('quality.qCategories')}>
          <div className="flex flex-wrap gap-2">
            {categories.map((category) => (
              <Chip key={category} selected={draft.categories.includes(category)} onToggle={() => toggleCategory(category)}>
                {categoryLabel(language, category)}
              </Chip>
            ))}
          </div>
        </Question>

        <Question title={t('quality.qClaim')}>
          <div role="radiogroup" aria-label={t('quality.qClaim')} className="grid gap-2 sm:grid-cols-2">
            {claimOptions.map(({ status, label }) => {
              const checked = draft.claim_status === status
              return (
                <button
                  key={status}
                  type="button"
                  role="radio"
                  aria-checked={checked}
                  onClick={() => setDraft((current) => ({ ...current, claim_status: status as ClaimStatus }))}
                  className={`flex items-center gap-2.5 rounded-control px-4 py-3 text-left text-[14px] font-medium ring-1 transition-all duration-150 ${
                    checked ? 'bg-accent-soft text-accent ring-accent/40' : 'bg-surface ring-ink/10 hover:ring-accent/30'
                  }`}
                >
                  <span
                    aria-hidden
                    className={`grid h-4.5 w-4.5 shrink-0 place-items-center rounded-full border-2 ${checked ? 'border-accent' : 'border-ink/25'}`}
                  >
                    {checked && <span className="h-2 w-2 rounded-full bg-accent" />}
                  </span>
                  {label}
                </button>
              )
            })}
          </div>
        </Question>

        <Question title={t('quality.notes')} htmlFor={`notes-${item.id}`}>
          <textarea
            id={`notes-${item.id}`}
            rows={2}
            maxLength={2000}
            value={draft.notes}
            placeholder={t('quality.notesPlaceholder')}
            onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
            className="w-full resize-y rounded-control border border-ink/10 bg-surface px-3.5 py-2.5 text-[14px] outline-none transition-shadow duration-150 placeholder:text-faint focus:border-accent/50 focus:ring-3 focus:ring-accent/15"
          />
        </Question>
      </div>

      <footer className="flex flex-wrap items-center gap-3 border-t border-line p-5 sm:px-8">
        <p role="status" aria-live="polite" className="text-[13.5px]">
          <AnimatePresence mode="wait">
            {missing ? (
              <m.span key="missing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-rumor">
                {t('quality.required')}
              </m.span>
            ) : saved ? (
              <m.span
                key="saved"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-1.5 font-medium text-confirmed"
              >
                <Check size={15} aria-hidden />
                {t('quality.saved')}
              </m.span>
            ) : save.isError || clear.isError ? (
              <span className="text-rumor">{t('error.save')}</span>
            ) : null}
          </AnimatePresence>
        </p>
        <span className="ml-auto flex flex-wrap gap-2">
          {item.annotation && (
            <button
              type="button"
              onClick={() => clear.mutate()}
              className="flex items-center gap-1.5 rounded-control px-3.5 py-2.5 text-[14px] font-semibold text-ink/60 transition-colors duration-150 hover:bg-canvas hover:text-ink"
            >
              <Eraser size={15} aria-hidden />
              {t('quality.clear')}
            </button>
          )}
          <button
            type="button"
            onClick={() => submit(false)}
            disabled={save.isPending}
            className="rounded-control bg-accent-soft px-4 py-2.5 text-[14px] font-semibold text-accent transition-colors duration-150 hover:bg-accent hover:text-on-fill disabled:opacity-60"
          >
            {t('quality.save')}
          </button>
          <button
            type="button"
            onClick={() => submit(true)}
            disabled={save.isPending}
            className="group flex items-center gap-1.5 rounded-control bg-accent px-5 py-2.5 text-[14px] font-semibold text-on-fill shadow-accent transition-all duration-150 ease-soft hover:-translate-y-0.5 hover:bg-accent-deep active:translate-y-0 disabled:opacity-60"
          >
            {t('quality.saveNext')}
            <ArrowRight size={15} aria-hidden className="transition-transform duration-150 ease-soft group-hover:translate-x-0.5" />
          </button>
        </span>
      </footer>
    </article>
  )
}

function Question({ title, htmlFor, children }: { title: string; htmlFor?: string; children: ReactNode }) {
  const Title = htmlFor ? 'label' : 'p'
  return (
    <div>
      <Title {...(htmlFor ? { htmlFor } : {})} className="mb-3 block text-[15px] font-semibold">
        {title}
      </Title>
      {children}
    </div>
  )
}

export function EmptyCard({ text }: { text: string }) {
  return (
    <div className="grid min-h-60 place-items-center rounded-card bg-surface/70 p-10 text-center shadow-card">
      <p className="max-w-sm text-[15px] text-muted">{text}</p>
    </div>
  )
}
