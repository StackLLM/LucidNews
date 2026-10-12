import { RefreshCw, ServerOff } from 'lucide-react'
import { m } from 'motion/react'
import type { ReactNode } from 'react'
import { ApiError } from '../lib/api'
import { useLanguage } from '../lib/i18n'
import { riseIn } from '../lib/motion'

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle: string; actions?: ReactNode }) {
  return (
    <m.header variants={riseIn} className="flex flex-wrap items-end justify-between gap-4 px-1">
      <div>
        <h1 className="font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em] sm:text-[40px]">{title}</h1>
        <p className="mt-1.5 text-[15px] text-muted">{subtitle}</p>
      </div>
      {actions}
    </m.header>
  )
}

/** API unreachable or missing data: explain what to do, offer a retry. */
export function ApiErrorCard({ error, onRetry, notFound }: { error: Error; onRetry: () => void; notFound?: string }) {
  const { t } = useLanguage()
  const isNotFound = error instanceof ApiError && error.status === 404
  return (
    <div role="alert" className="mx-auto mt-10 max-w-lg rounded-card bg-surface p-8 text-center shadow-card">
      <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-accent-soft text-accent">
        <ServerOff size={22} aria-hidden />
      </span>
      <h1 className="mt-4 text-lg font-bold">{isNotFound ? (notFound ?? t('state.notFound')) : t('state.errorTitle')}</h1>
      {!isNotFound && (
        <>
          <p className="mt-2 text-sm text-muted">{t('state.errorBody')}</p>
          <code className="mt-4 block rounded-control bg-canvas px-4 py-3 text-[13px] text-ink/80">uv run lucidnews-api</code>
        </>
      )}
      <button
        type="button"
        onClick={onRetry}
        className="mt-6 inline-flex items-center gap-2 rounded-control bg-accent px-5 py-2.5 text-sm font-semibold text-on-fill shadow-accent transition-all duration-150 ease-soft hover:-translate-y-0.5 hover:bg-accent-deep active:translate-y-0 active:scale-[0.98]"
      >
        <RefreshCw size={15} aria-hidden />
        {t('state.retry')}
      </button>
    </div>
  )
}

export function PageSkeleton({ blocks = 3 }: { blocks?: number }) {
  const { t } = useLanguage()
  return (
    <div role="status" aria-live="polite" className="space-y-6">
      <span className="sr-only">{t('page.loading')}</span>
      <div className="h-16 w-72 animate-shimmer rounded-card bg-surface/60" />
      {Array.from({ length: blocks }, (_, index) => (
        <div key={index} className="h-48 animate-shimmer rounded-card bg-surface/80 shadow-card" />
      ))}
    </div>
  )
}

/** Segmented control (pill buttons) used for filters and periods. */
export function Segmented<T extends string | number>({
  label,
  value,
  options,
  onChange,
  id,
}: {
  label: string
  value: T
  options: { value: T; label: ReactNode }[]
  onChange: (value: T) => void
  id: string
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex max-w-full flex-wrap gap-1 rounded-full bg-surface/70 p-1 shadow-card ring-1 ring-ink/[0.04]">
      {options.map((option) => (
        <button
          key={String(option.value)}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
          className="relative rounded-full px-3.5 py-1.5 text-[13px] font-semibold text-muted transition-colors duration-150 hover:text-ink aria-pressed:text-on-fill"
        >
          {option.value === value && (
            <m.span
              layoutId={`segmented-${id}`}
              transition={{ type: 'spring', stiffness: 380, damping: 32 }}
              className="absolute inset-0 rounded-full bg-ink"
            />
          )}
          <span className="relative flex items-center gap-1.5">{option.label}</span>
        </button>
      ))}
    </div>
  )
}
