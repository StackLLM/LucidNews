import { Crown } from 'lucide-react'
import type { PreferenceOptions, Subscriber } from '../../lib/api'
import { useLanguage, type MessageKey } from '../../lib/i18n'

/** Free / Premium, displayed only: no payment, no paywall at this stage. */
export function PlanCard({ plans, current }: { plans: PreferenceOptions['plans']; current?: Subscriber['plan'] }) {
  const { t } = useLanguage()
  return (
    <section aria-labelledby="plan-title" className="glass rounded-card p-5">
      <h2 id="plan-title" className="px-1 text-[15px] font-bold">
        {t('prefs.plan')}
      </h2>
      <ul className="mt-3 grid grid-cols-2 gap-2.5">
        {plans.map((plan) => {
          const unlimited = plan.max_categories === null && plan.max_sources === null && plan.max_items === null
          const isCurrent = plan.id === current
          return (
            <li key={plan.id} className={`rounded-control p-3.5 ${isCurrent ? 'bg-surface shadow-card ring-1 ring-accent/25' : 'bg-surface/50'}`}>
              <p className="flex items-center gap-1.5 text-[14px] font-bold">
                {plan.id === 'premium' && <Crown size={14} className="text-unverified" aria-hidden />}
                {t(`prefs.plan.${plan.id}` as MessageKey)}
              </p>
              <p className="mt-1 text-[12px] leading-snug text-muted">{unlimited ? t('prefs.unlimited') : '—'}</p>
              {isCurrent && (
                <span className="mt-2 inline-block rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent">{t('prefs.current')}</span>
              )}
            </li>
          )
        })}
      </ul>
      <p className="mt-3 px-1 text-[12px] leading-relaxed text-muted">{t('prefs.planNote')}</p>
    </section>
  )
}
