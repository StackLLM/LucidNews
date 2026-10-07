import { BadgeCheck, CircleHelp, ShieldCheck, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { ReliabilityLabel } from '../lib/api'
import { labelHintKey, labelKey, useLanguage } from '../lib/i18n'

// Colour + icon + text: the label must stay readable without colour.
export const reliabilityStyles: Record<ReliabilityLabel, { icon: LucideIcon; tone: string; dot: string }> = {
  confirmed: { icon: ShieldCheck, tone: 'bg-confirmed/10 text-confirmed ring-confirmed/20', dot: 'bg-confirmed' },
  reliable: { icon: BadgeCheck, tone: 'bg-reliable/10 text-reliable ring-reliable/20', dot: 'bg-reliable' },
  unverified: { icon: CircleHelp, tone: 'bg-unverified/10 text-unverified ring-unverified/25', dot: 'bg-unverified' },
  rumor: { icon: TriangleAlert, tone: 'bg-rumor/10 text-rumor ring-rumor/25', dot: 'bg-rumor' },
}

export function ReliabilityBadge({ label }: { label: ReliabilityLabel }) {
  const { t } = useLanguage()
  const { icon: Icon, tone } = reliabilityStyles[label]
  return (
    <span
      title={t(labelHintKey(label))}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12.5px] font-semibold ring-1 ring-inset ${tone}`}
    >
      <Icon size={14} strokeWidth={2.25} aria-hidden />
      {t(labelKey(label))}
    </span>
  )
}
