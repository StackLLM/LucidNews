import { Check } from 'lucide-react'
import type { ReactNode } from 'react'

/** Toggle chip for multi-select lists (aria-pressed). */
export function Chip({ selected, onToggle, children }: { selected: boolean; onToggle: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onToggle}
      className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-[13px] font-medium ring-1 transition-all duration-150 ease-soft active:scale-[0.97] ${
        selected
          ? 'bg-accent text-on-fill ring-accent shadow-[0_6px_16px_-8px_rgb(76_63_216/0.6)]'
          : 'bg-surface text-ink/75 ring-ink/10 hover:ring-accent/40 hover:text-ink'
      }`}
    >
      {selected && <Check size={13} strokeWidth={2.5} aria-hidden />}
      {children}
    </button>
  )
}
