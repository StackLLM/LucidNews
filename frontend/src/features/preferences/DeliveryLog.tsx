import { useQuery } from '@tanstack/react-query'
import { Check, ScrollText, X } from 'lucide-react'
import { fetchDeliveries, type Delivery } from '../../lib/api'
import { formatEditionDate, formatItemTime } from '../../lib/format'
import { useLanguage, type MessageKey } from '../../lib/i18n'

/** Every e-mail sent to one reader, or to everyone: who, when, which edition, result. */
export function DeliveryLog({ subscriberId }: { subscriberId?: string }) {
  const { language, t } = useLanguage()
  const log = useQuery({ queryKey: ['deliveries', subscriberId ?? 'all'], queryFn: ({ signal }) => fetchDeliveries(subscriberId, signal) })

  return (
    <section aria-labelledby="log-title" className="rounded-card bg-surface shadow-card">
      <header className="flex items-center gap-4 p-5 sm:p-7">
        <span aria-hidden className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
          <ScrollText size={20} />
        </span>
        <div className="min-w-0">
          <h2 id="log-title" className="text-[17px] font-bold">
            {t('log.title')}
          </h2>
          <p className="text-[13px] text-muted">{t('log.subtitle')}</p>
        </div>
      </header>
      <div className="border-t border-line px-5 py-3 sm:px-7">
        {log.isPending && <p className="py-3 text-[14px] text-muted">{t('preview.loading')}</p>}
        {log.isError && <p role="alert" className="py-3 text-[14px] text-rumor">{t('log.error')}</p>}
        {log.data && log.data.length === 0 && <p className="py-3 text-[14px] text-muted">{t('log.empty')}</p>}
        {log.data && log.data.length > 0 && (
          <ul className="divide-y divide-line/70">
            {log.data.map((delivery) => (
              <Row key={delivery.id} delivery={delivery} showEmail={!subscriberId} language={language} />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function Row({ delivery, showEmail, language }: { delivery: Delivery; showEmail: boolean; language: 'en' | 'fr' }) {
  const { t } = useLanguage()
  const ok = delivery.status === 'sent'
  const reference =
    delivery.kind === 'weekly' && delivery.reference
      ? t('log.week', { date: formatEditionDate(delivery.reference, language) })
      : delivery.kind === 'daily' && delivery.reference
        ? delivery.reference
        : null
  return (
    <li className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 gap-y-0.5 py-3 text-[13.5px]">
      <span
        className={`mt-0.5 grid h-6 w-6 place-items-center rounded-full ring-1 ring-inset ${ok ? 'bg-confirmed/10 text-confirmed ring-confirmed/25' : 'bg-rumor/10 text-rumor ring-rumor/25'}`}
      >
        {ok ? <Check size={13} strokeWidth={2.5} aria-hidden /> : <X size={13} strokeWidth={2.5} aria-hidden />}
        <span className="sr-only">{ok ? t('log.sent') : t('log.failed')}</span>
      </span>
      <div className="min-w-0">
        <p className="truncate font-semibold">
          {t(`log.kind.${delivery.kind}` as MessageKey)}
          {showEmail && <span className="ml-2 font-medium text-muted">{delivery.email}</span>}
        </p>
        <p className="truncate text-[12.5px] text-muted" title={delivery.subject}>
          {delivery.subject}
          {reference && ` · ${reference}`}
        </p>
        {delivery.error && <p className="text-[12.5px] text-rumor [overflow-wrap:anywhere]">{delivery.error}</p>}
      </div>
      <time dateTime={delivery.created_at} className="text-[12.5px] text-faint tabular-nums">
        {formatItemTime(delivery.created_at, language)}
      </time>
    </li>
  )
}
