import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Clock, MailX, Send } from 'lucide-react'
import { useState } from 'react'
import { useLocation } from 'react-router'
import { resendConfirmation, type Confirmation, type Subscriber } from '../../lib/api'
import { formatEditionDate } from '../../lib/format'
import { useLanguage, type MessageKey } from '../../lib/i18n'

export const statusStyles = {
  pending: { icon: Clock, tone: 'bg-unverified/10 text-unverified ring-unverified/25' },
  confirmed: { icon: CheckCircle2, tone: 'bg-confirmed/10 text-confirmed ring-confirmed/25' },
  unsubscribed: { icon: MailX, tone: 'bg-ink/[0.06] text-ink/60 ring-ink/10' },
} as const

/** Icon + text, never colour alone. */
export function StatusBadge({ status }: { status: Subscriber['status'] }) {
  const { t } = useLanguage()
  const { icon: Icon, tone } = statusStyles[status]
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11.5px] font-semibold whitespace-nowrap ring-1 ring-inset ${tone}`}>
      <Icon size={12} strokeWidth={2.25} aria-hidden />
      {t(`status.${status}` as MessageKey)}
    </span>
  )
}

/** What the reader's status means for what they receive, and how to move a pending one forward. */
export function SubscriptionStatus({ subscriber }: { subscriber: Subscriber }) {
  const { language, t } = useLanguage()
  const queryClient = useQueryClient()
  // Right after "Add", the result of the first confirmation link arrives with the navigation.
  const initial = (useLocation().state as { confirmation?: Confirmation } | null)?.confirmation ?? null
  const [result, setResult] = useState<Confirmation | null>(initial)
  const resend = useMutation({
    mutationFn: () => resendConfirmation(subscriber.id),
    onSuccess: async (updated) => {
      setResult(updated.confirmation)
      await queryClient.invalidateQueries({ queryKey: ['subscribers'] })
      await queryClient.invalidateQueries({ queryKey: ['deliveries'] })
    },
    onError: () => setResult({ sent: false, error: t('error.save') }),
  })

  const { status } = subscriber
  const date = (iso: string | null) => (iso ? formatEditionDate(iso, language) : '')
  const body =
    status === 'pending'
      ? t('status.pendingBody')
      : status === 'unsubscribed'
        ? t('status.unsubscribedBody', { date: date(subscriber.unsubscribed_at) })
        : subscriber.confirmed_at
          ? t('status.confirmedBody', { date: date(subscriber.confirmed_at) })
          : t('status.confirmedLegacy')

  return (
    <section aria-label={t(`status.${status}` as MessageKey)} className="flex flex-wrap items-center gap-3 rounded-card bg-surface px-5 py-4 shadow-card sm:px-7">
      <StatusBadge status={status} />
      <p className="min-w-[14rem] flex-1 text-[13.5px] text-muted">{body}</p>
      {status !== 'confirmed' && (
        <button
          type="button"
          disabled={resend.isPending}
          onClick={() => resend.mutate()}
          className="flex items-center gap-1.5 rounded-control bg-accent-soft px-3.5 py-2 text-[13.5px] font-semibold text-accent transition-colors duration-150 hover:bg-accent hover:text-white disabled:opacity-60"
        >
          <Send size={14} aria-hidden />
          {result ? t('status.resendAgain') : t('status.resend')}
        </button>
      )}
      {result && (
        <p role="status" className={`w-full text-[13px] ${result.sent ? 'text-confirmed' : 'text-rumor'}`}>
          {result.sent ? t('status.sent') : t('status.failed', { error: result.error ?? '' })}
        </p>
      )}
    </section>
  )
}
