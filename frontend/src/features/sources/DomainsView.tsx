import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, CircleCheck, CircleSlash, Plus, Sparkles, TriangleAlert } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useId, useState } from 'react'
import { inputClass, primaryButton } from '../../design/Field'
import { ApiErrorCard, PageSkeleton } from '../../design/PageState'
import { Switch } from '../../design/Switch'
import {
  addSource,
  ApiError,
  fetchCatalog,
  fetchCoverage,
  fetchSourceConfig,
  saveSomeSettings,
  testSource,
  type CatalogEntry,
  type Coverage,
  type DomainCoverage,
  type SourceTest,
} from '../../lib/api'
import { formatItemTime, formatPercent, sourceName } from '../../lib/format'
import { categoryLabel, translatePlural, useLanguage } from '../../lib/i18n'
import { listStagger, riseIn, useMotionPreference } from '../../lib/motion'
import { kindKey } from './sourceFields'
import { TestBlock } from './SourcePanel'

/** `rss/LWN.net` -> `LWN.net`, `github/@karpathy` -> `@karpathy`, `hackernews` -> `Hacker News`. */
export function keyLabel(key: string): string {
  const slash = key.indexOf('/')
  return slash < 0 ? sourceName(key) : key.slice(slash + 1)
}

type Notice = { text: string; error?: boolean } | null

/**
 * Coverage of the 12 categories, computed by the API from the archive only, and
 * catalog sources that are not configured yet. Writes need the local API.
 */
export function DomainsView({ days }: { days: number }) {
  const { t } = useLanguage()
  const { enabled } = useMotionPreference()
  const queryClient = useQueryClient()
  const [notice, setNotice] = useState<Notice>(null)
  const coverage = useQuery({
    queryKey: ['coverage', days],
    queryFn: ({ signal }) => fetchCoverage(days, signal),
    placeholderData: keepPreviousData,
  })
  const catalog = useQuery({ queryKey: ['catalog'], queryFn: ({ signal }) => fetchCatalog(signal) })
  // Same file version as the settings: present only on the local API.
  const config = useQuery({
    queryKey: ['source-config'],
    queryFn: ({ signal }) => fetchSourceConfig(signal),
    retry: (failures, error) => !(error instanceof ApiError && error.status === 403) && failures < 2,
  })
  const version = config.data?.version ?? null

  useEffect(() => {
    if (!notice || notice.error) return
    const timer = window.setTimeout(() => setNotice(null), 4000)
    return () => window.clearTimeout(timer)
  }, [notice])

  const refresh = () =>
    Promise.all(
      [['source-config'], ['coverage'], ['catalog'], ['settings'], ['sources']].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    )
  const failed = (error: Error) => {
    const conflict = error instanceof ApiError && error.status === 409 && !Object.keys(error.fields).length
    const field = error instanceof ApiError ? Object.values(error.fields)[0] : undefined
    setNotice({
      text: conflict ? t('sources.conflict') : field ? t('sources.serverError', { message: field }) : t('error.save'),
      error: true,
    })
    if (conflict) config.refetch()
  }

  const saveDigest = useMutation({
    mutationFn: (digest: Record<string, unknown>) => saveSomeSettings(version!, { digest }),
    onSuccess: async () => {
      setNotice({ text: t('domains.saved') })
      await refresh()
    },
    onError: failed,
  })
  const add = useMutation({
    mutationFn: (entry: CatalogEntry) => addSource(version!, entry.kind, entry.values),
    onSuccess: async (_, entry) => {
      setNotice({ text: t('sources.added', { name: entry.label }) })
      await refresh()
    },
    onError: failed,
  })

  if (coverage.isPending) return <PageSkeleton />
  if (coverage.isError) return <ApiErrorCard error={coverage.error} onRetry={() => coverage.refetch()} />
  const data = coverage.data
  const watched = data.categories.filter((entry) => entry.watched)
  const tiles = [
    { label: t('domains.watched'), value: `${watched.length}/${data.categories.length}` },
    { label: t('domains.covered'), value: watched.filter((entry) => !entry.gap).length, tone: 'text-confirmed' },
    { label: t('domains.gaps'), value: watched.filter((entry) => entry.gap).length, tone: 'text-rumor' },
    { label: t('domains.analyzed'), value: data.analyzed },
  ]
  const toggleWatch = (category: string, follow: boolean) => {
    const next = follow ? [...data.watched, category] : data.watched.filter((entry) => entry !== category)
    saveDigest.mutate({ watched_categories: next })
  }
  const busy = saveDigest.isPending || add.isPending

  return (
    <motion.div variants={listStagger} initial={enabled ? 'hidden' : false} animate="visible" className="space-y-6">
      <motion.dl variants={riseIn} className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        {tiles.map((tile) => (
          <div key={tile.label} className="glass rounded-card px-5 py-4">
            <dt className="text-[13px] font-medium text-muted">{tile.label}</dt>
            <dd
              className={`mt-1 text-[32px] leading-none font-bold ${
                tile.tone && typeof tile.value === 'number' && tile.value > 0 ? tile.tone : 'text-ink'
              }`}
            >
              {tile.value}
            </dd>
          </div>
        ))}
      </motion.dl>

      <motion.div variants={riseIn}>
        {version ? (
          <OptionsCard coverage={data} busy={busy} onSave={(digest) => saveDigest.mutate(digest)} />
        ) : (
          !config.isPending && <p className="rounded-control bg-white/70 px-4 py-3 text-[13.5px] text-muted">{t('domains.localOnly')}</p>
        )}
      </motion.div>

      <motion.p variants={riseIn} role="status" aria-live="polite" className={`text-[13.5px] font-medium empty:hidden ${notice?.error ? 'text-rumor' : 'text-confirmed'}`}>
        {notice?.text ?? ''}
      </motion.p>

      <motion.ul variants={riseIn} className="grid items-start gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {data.categories.map((domain) => (
          <DomainCard
            key={domain.category}
            domain={domain}
            coverage={data}
            recommended={(catalog.data ?? []).filter((entry) => entry.category === domain.category)}
            editable={version !== null}
            busy={busy}
            onFollow={(follow) => toggleWatch(domain.category, follow)}
            onAdd={(entry) => add.mutate(entry)}
          />
        ))}
      </motion.ul>

      <motion.div variants={riseIn} className="space-y-1 text-[12.5px] leading-relaxed text-muted">
        <p>{t('domains.source')}</p>
        {data.uncategorized > 0 && <p>{t('domains.uncategorized', { count: data.uncategorized })}</p>}
        {data.unanalyzed > 0 && <p>{t('domains.unanalyzed', { count: data.unanalyzed })}</p>}
      </motion.div>
    </motion.div>
  )
}

function OptionsCard({
  coverage,
  busy,
  onSave,
}: {
  coverage: Coverage
  busy: boolean
  onSave: (digest: Record<string, unknown>) => void
}) {
  const { t } = useLanguage()
  const id = useId()
  const [minSources, setMinSources] = useState(String(coverage.min_sources))
  const [minItems, setMinItems] = useState(String(coverage.min_items))
  useEffect(() => {
    setMinSources(String(coverage.min_sources))
    setMinItems(String(coverage.min_items))
  }, [coverage.min_sources, coverage.min_items])

  const sources = Number(minSources)
  const items = Number(minItems)
  const valid =
    minSources !== '' && minItems !== '' && Number.isInteger(sources) && Number.isInteger(items) &&
    sources >= 0 && sources <= 50 && items >= 0 && items <= 1000
  const dirty = sources !== coverage.min_sources || items !== coverage.min_items

  return (
    <section aria-labelledby={`${id}-title`} className="rounded-card bg-surface p-5 shadow-card sm:p-7">
      <h2 id={`${id}-title`} className="text-[17px] font-bold">
        {t('domains.options')}
      </h2>
      <div className="mt-4 flex items-start gap-3">
        <Switch
          checked={coverage.only_watched}
          disabled={busy || (!coverage.only_watched && coverage.watched.length === 0)}
          labelledBy={`${id}-only`}
          describedBy={`${id}-only-hint`}
          onCheckedChange={(checked) => onSave({ only_watched_categories: checked })}
        />
        <div>
          <p id={`${id}-only`} className="text-[14px] font-semibold text-ink/85">
            {t('domains.onlyWatched')}
          </p>
          <p id={`${id}-only-hint`} className="mt-0.5 text-[12.5px] leading-snug text-muted">
            {t('domains.onlyWatchedHint')}
          </p>
        </div>
      </div>
      <form
        className="mt-5 flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (valid && dirty) onSave({ coverage_min_sources: sources, coverage_min_items: items })
        }}
      >
        <label className="w-full text-[13px] font-semibold text-ink/85 sm:w-56">
          {t('domains.minSources')}
          <input
            type="number"
            min={0}
            max={50}
            inputMode="numeric"
            value={minSources}
            onChange={(event) => setMinSources(event.target.value)}
            className={`${inputClass} mt-1.5`}
          />
        </label>
        <label className="w-full text-[13px] font-semibold text-ink/85 sm:w-56">
          {t('domains.minItems')}
          <input
            type="number"
            min={0}
            max={1000}
            inputMode="numeric"
            value={minItems}
            onChange={(event) => setMinItems(event.target.value)}
            className={`${inputClass} mt-1.5`}
          />
        </label>
        <button type="submit" disabled={busy || !valid || !dirty} className={primaryButton}>
          {t('domains.save')}
        </button>
        <p className="w-full text-[12.5px] text-muted">{t('domains.thresholdHint')}</p>
      </form>
    </section>
  )
}

function DomainCard({
  domain,
  coverage,
  recommended,
  editable,
  busy,
  onFollow,
  onAdd,
}: {
  domain: DomainCoverage
  coverage: Coverage
  recommended: CatalogEntry[]
  editable: boolean
  busy: boolean
  onFollow: (follow: boolean) => void
  onAdd: (entry: CatalogEntry) => void
}) {
  const { language, t } = useLanguage()
  const [open, setOpen] = useState(false)
  const name = categoryLabel(language, domain.category)
  const listId = useId()
  const state = !domain.watched
    ? { icon: CircleSlash, label: t('domains.state.unwatched'), tone: 'bg-ink/[0.06] text-ink/60 ring-ink/10' }
    : domain.gap
      ? { icon: TriangleAlert, label: t('domains.state.gap'), tone: 'bg-rumor/10 text-rumor ring-rumor/20' }
      : { icon: CircleCheck, label: t('domains.state.covered'), tone: 'bg-confirmed/10 text-confirmed ring-confirmed/20' }
  const StateIcon = state.icon
  // Removing the last followed domain would empty the digest when only those are published.
  const lastFollowed = coverage.only_watched && domain.watched && coverage.watched.length === 1

  return (
    <li className={`flex flex-col rounded-card bg-surface p-5 shadow-card ${domain.watched ? '' : 'opacity-80'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[16px] font-bold">{name}</h3>
          <span className={`mt-1.5 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12.5px] font-semibold ring-1 ring-inset ${state.tone}`}>
            <StateIcon size={14} strokeWidth={2.25} aria-hidden />
            {state.label}
          </span>
        </div>
        {editable && (
          <Switch
            checked={domain.watched}
            disabled={busy || lastFollowed}
            label={t('domains.follow', { name })}
            onCheckedChange={onFollow}
          />
        )}
      </div>

      {domain.gap && (
        <ul className="mt-3 space-y-0.5 text-[13px] font-medium text-rumor">
          {domain.gap_reasons.map((reason) => (
            <li key={reason}>
              {reason === 'sources'
                ? t('domains.reason.sources', { min: coverage.min_sources })
                : t('domains.reason.items', { min: coverage.min_items, days: coverage.days })}
            </li>
          ))}
        </ul>
      )}

      {domain.items === 0 ? (
        <p className="mt-3 text-[13.5px] text-muted">{t('domains.none')}</p>
      ) : (
        <div className="mt-3 space-y-1 text-[13px] text-muted">
          <p className="tabular-nums">
            {t('domains.stats', { items: domain.items, published: domain.published, sources: domain.active_sources })}
          </p>
          <p>
            {domain.trusted_share !== null && t('domains.trusted', { share: formatPercent(domain.trusted_share, language) })}
            {domain.latest_at && <> · {t('domains.latest', { time: formatItemTime(domain.latest_at, language) })}</>}
          </p>
          <ul className="flex flex-wrap gap-1.5 pt-1.5">
            {domain.sources.map((source) => (
              <li
                key={source.source}
                className={`max-w-full truncate rounded-full px-2.5 py-0.5 text-[12px] ${
                  source.configured ? 'bg-canvas text-ink/75' : 'bg-canvas/60 text-faint line-through decoration-faint/60'
                }`}
                title={source.configured ? undefined : t('domains.notConfigured')}
              >
                {keyLabel(source.source)} · {source.items}
                {!source.configured && <span className="sr-only"> ({t('domains.notConfigured')})</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-auto pt-4">
        {recommended.length === 0 ? (
          <p className="text-[12.5px] text-faint">{t('domains.noRecommendation')}</p>
        ) : (
          <>
            <button
              type="button"
              aria-expanded={open}
              aria-controls={listId}
              onClick={() => setOpen((value) => !value)}
              className="flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1.5 text-[13px] font-semibold text-accent transition-colors duration-150 hover:bg-accent hover:text-white"
            >
              <Sparkles size={14} aria-hidden />
              {translatePlural(language, 'domains.recommended', recommended.length, { count: recommended.length })}
              <ChevronDown size={14} aria-hidden className={`transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
            </button>
            <AnimatePresence initial={false}>
              {open && (
                <motion.ul
                  id={listId}
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                  className="mt-3 space-y-3 overflow-hidden"
                >
                  {recommended.map((entry) => (
                    <Recommendation key={entry.key} entry={entry} editable={editable} busy={busy} onAdd={() => onAdd(entry)} />
                  ))}
                </motion.ul>
              )}
            </AnimatePresence>
          </>
        )}
      </div>
    </li>
  )
}

function Recommendation({
  entry,
  editable,
  busy,
  onAdd,
}: {
  entry: CatalogEntry
  editable: boolean
  busy: boolean
  onAdd: () => void
}) {
  const { t } = useLanguage()
  const [result, setResult] = useState<SourceTest | null>(null)
  const run = useMutation({
    mutationFn: () => testSource({ kind: entry.kind, values: entry.values }),
    onMutate: () => setResult(null),
    onSuccess: setResult,
  })

  return (
    <li className="rounded-2xl bg-canvas/70 p-3.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[14px] font-semibold" title={entry.label}>
            {entry.label}
          </p>
          <p className="text-[12px] text-faint">{t(kindKey(entry.kind))}</p>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 text-[11.5px] font-semibold whitespace-nowrap text-muted ring-1 ring-ink/10 ring-inset">
          {t('domains.badge')}
        </span>
      </div>
      {entry.description && <p className="mt-1.5 text-[12.5px] leading-snug text-muted">{entry.description}</p>}
      {editable && (
        <div className="mt-3 space-y-2">
          <TestBlock running={run.isPending} result={result} onRun={() => run.mutate()} />
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={onAdd} disabled={busy || result === null} className={`${primaryButton} py-2 text-[13px]`}>
              <Plus size={14} aria-hidden />
              {t('domains.add')}
            </button>
            {result === null && <span className="text-[12px] text-faint">{t('domains.addHint')}</span>}
            {run.isError && (
              <span role="alert" className="text-[12px] text-rumor">
                {t('sources.test.failed', { error: run.error.message })}
              </span>
            )}
          </div>
        </div>
      )}
    </li>
  )
}
