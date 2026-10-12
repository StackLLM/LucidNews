import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Inbox, UserPlus } from 'lucide-react'
import { m } from 'motion/react'
import { useForm } from 'react-hook-form'
import { NavLink, useNavigate, useParams } from 'react-router'
import { z } from 'zod'
import { ApiErrorCard, PageHeader, PageSkeleton } from '../../design/PageState'
import { ApiError, createSubscriber, fetchPreferenceOptions, fetchSubscribers, type PreferenceOptions, type Subscriber } from '../../lib/api'
import { useLanguage, type MessageKey } from '../../lib/i18n'
import { listStagger, riseIn, useMotionPreference } from '../../lib/motion'
import { DeliveryLog } from './DeliveryLog'
import { NewsletterPreview } from './NewsletterPreview'
import { PlanCard } from './PlanCard'
import { PreferencesForm } from './PreferencesForm'
import { StatusBadge, SubscriptionStatus } from './SubscriptionStatus'

export function PreferencesPage() {
  const options = useQuery({ queryKey: ['preference-options'], queryFn: ({ signal }) => fetchPreferenceOptions(signal) })
  const subscribers = useQuery({ queryKey: ['subscribers'], queryFn: ({ signal }) => fetchSubscribers(signal) })

  if (options.isPending || subscribers.isPending) return <PageSkeleton blocks={2} />
  if (options.isError) return <ApiErrorCard error={options.error} onRetry={() => options.refetch()} />
  if (subscribers.isError) return <ApiErrorCard error={subscribers.error} onRetry={() => subscribers.refetch()} />
  return <PreferencesView options={options.data} subscribers={subscribers.data} />
}

function PreferencesView({ options, subscribers }: { options: PreferenceOptions; subscribers: Subscriber[] }) {
  const { t } = useLanguage()
  const { enabled } = useMotionPreference()
  const { subscriberId } = useParams()
  const selected = subscribers.find((subscriber) => subscriber.id === subscriberId)

  return (
    <m.div variants={listStagger} initial={enabled ? 'hidden' : false} animate="visible" className="space-y-8">
      <PageHeader title={t('prefs.title')} subtitle={t('prefs.subtitle')} />

      {/* DOM order = phone order (list, form, plan); the grid puts the plan under the list on desktop. */}
      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)] lg:grid-rows-[auto_1fr] lg:gap-x-8">
        <m.div variants={riseIn} className="self-start lg:col-start-1 lg:row-start-1">
          <SubscriberList subscribers={subscribers} selectedId={selected?.id} />
        </m.div>

        <m.div variants={riseIn} className="min-w-0 space-y-6 lg:col-start-2 lg:row-span-2 lg:row-start-1">
          {selected ? (
            <>
              <SubscriptionStatus key={`status-${selected.id}-${selected.status}`} subscriber={selected} />
              <PreferencesForm key={selected.id} subscriber={selected} options={options} />
              <NewsletterPreview key={`preview-${selected.id}`} subscriber={selected} />
              <DeliveryLog key={`log-${selected.id}`} subscriberId={selected.id} />
            </>
          ) : (
            <>
              <div className="grid min-h-72 place-items-center rounded-card bg-surface/70 p-10 text-center shadow-card">
                <div>
                  <span className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-accent-soft text-accent">
                    <Inbox size={24} aria-hidden />
                  </span>
                  <p className="mx-auto mt-4 max-w-sm text-[15px] text-muted">{subscriberId ? t('prefs.notFound') : t('prefs.pick')}</p>
                </div>
              </div>
              <DeliveryLog />
            </>
          )}
        </m.div>

        <m.div variants={riseIn} className="self-start lg:col-start-1 lg:row-start-2">
          <PlanCard plans={options.plans} current={selected?.plan} />
        </m.div>
      </div>
    </m.div>
  )
}

function SubscriberList({ subscribers, selectedId }: { subscribers: Subscriber[]; selectedId?: string }) {
  const { language, t } = useLanguage()
  return (
    <section aria-labelledby="subscribers-title" className="glass rounded-card p-5">
      <h2 id="subscribers-title" className="flex items-center justify-between px-1 text-[15px] font-bold">
        {t('prefs.subscribers')}
        <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[12px] text-accent tabular-nums">{subscribers.length}</span>
      </h2>

      {subscribers.length === 0 ? (
        <p className="mt-3 px-1 text-[13.5px] text-muted">{t('prefs.empty')}</p>
      ) : (
        <ul className="mt-3 max-h-[22rem] space-y-1 overflow-y-auto">
          {subscribers.map((subscriber) => {
            const active = subscriber.id === selectedId
            return (
              <li key={subscriber.id}>
                <NavLink
                  to={{ pathname: `/preferences/${subscriber.id}`, search: `?lang=${language}` }}
                  aria-current={active ? 'page' : undefined}
                  className={`flex items-center gap-3 rounded-control px-3 py-2.5 transition-all duration-150 ${
                    active ? 'bg-surface shadow-card ring-1 ring-accent/25' : 'hover:bg-surface/70'
                  }`}
                >
                  <span
                    aria-hidden
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent-soft text-[14px] font-bold uppercase text-accent"
                  >
                    {subscriber.email.charAt(0)}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[14px] font-semibold">{subscriber.email}</span>
                    <span className="block text-[12px] uppercase tracking-wide text-faint">
                      {subscriber.preferences.language} · {t(`freq.${subscriber.preferences.frequency}` as MessageKey)}
                    </span>
                    {subscriber.status !== 'confirmed' && (
                      <span className="mt-1 block">
                        <StatusBadge status={subscriber.status} />
                      </span>
                    )}
                  </span>
                </NavLink>
              </li>
            )
          })}
        </ul>
      )}

      <AddSubscriber />
    </section>
  )
}

const addSchema = z.object({ email: z.email({ error: 'email' }) })

function AddSubscriber() {
  const { language, t } = useLanguage()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const form = useForm<z.infer<typeof addSchema>>({ resolver: zodResolver(addSchema), defaultValues: { email: '' } })
  const mutation = useMutation({
    mutationFn: (email: string) => createSubscriber(email),
    onSuccess: async (subscriber) => {
      await queryClient.invalidateQueries({ queryKey: ['subscribers'] })
      form.reset()
      // The first confirmation link's result is shown on the new reader's page.
      navigate({ pathname: `/preferences/${subscriber.id}`, search: `?lang=${language}` }, { state: { confirmation: subscriber.confirmation } })
    },
    onError: (error) => {
      const message =
        error instanceof ApiError && error.status === 409
          ? t('error.exists')
          : error instanceof ApiError && error.fields.email
            ? t('error.email')
            : t('error.save')
      form.setError('email', { message })
    },
  })
  const error = form.formState.errors.email

  return (
    <form noValidate onSubmit={form.handleSubmit(({ email }) => mutation.mutate(email.trim()))} className="mt-4 border-t border-ink/[0.06] pt-4">
      <label htmlFor="new-subscriber" className="px-1 text-[12px] font-semibold uppercase tracking-[0.08em] text-faint">
        {t('prefs.addLabel')}
      </label>
      <div className="mt-2 flex gap-2">
        <input
          id="new-subscriber"
          type="email"
          autoComplete="off"
          placeholder={t('prefs.addPlaceholder')}
          aria-invalid={!!error}
          aria-describedby={error ? 'new-subscriber-error' : undefined}
          {...form.register('email')}
          className="min-w-0 flex-1 rounded-control border border-ink/10 bg-surface px-3.5 py-2.5 text-[14px] outline-none transition-shadow duration-150 placeholder:text-faint focus:border-accent/50 focus:ring-3 focus:ring-accent/15 aria-invalid:border-rumor/50"
        />
        <button
          type="submit"
          disabled={mutation.isPending}
          className="flex items-center gap-1.5 rounded-control bg-accent-soft px-3.5 text-[14px] font-semibold text-accent transition-colors duration-150 hover:bg-accent hover:text-on-fill disabled:opacity-60"
        >
          <UserPlus size={16} aria-hidden />
          {t('prefs.add')}
        </button>
      </div>
      {error && (
        <p id="new-subscriber-error" role="alert" className="mt-2 px-1 text-[13px] text-rumor">
          {error.message === 'email' ? t('error.email') : error.message}
        </p>
      )}
    </form>
  )
}
