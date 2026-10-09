import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { useParams } from 'react-router'
import { ApiErrorCard } from '../../design/PageState'
import { fetchEdition, type Edition } from '../../lib/api'
import { useLanguage } from '../../lib/i18n'
import { listStagger, riseIn, useMotionPreference } from '../../lib/motion'
import { EditionHero } from './EditionHero'
import { EditionSidebar } from './EditionSidebar'
import { ItemCard } from './ItemCard'
import { UnanalyzedSection } from './UnanalyzedSection'

export function EditionPage() {
  const { editionId = 'latest' } = useParams()
  const { language } = useLanguage()
  const query = useQuery({
    queryKey: ['edition', editionId, language],
    queryFn: ({ signal }) => fetchEdition(editionId, language, signal),
    placeholderData: (previous) => previous, // keep the page while switching language
  })

  if (query.isPending) return <EditionSkeleton />
  if (query.isError) return <ApiErrorCard error={query.error} onRetry={() => query.refetch()} />
  return <EditionView key={query.data.id} edition={query.data} archived={editionId !== 'latest'} />
}

function EditionView({ edition, archived }: { edition: Edition; archived: boolean }) {
  const { enabled } = useMotionPreference()
  return (
    <motion.div
      variants={listStagger}
      // Animations off: render the final state directly (children inherit it).
      initial={enabled ? 'hidden' : false}
      animate="visible"
      className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px] xl:gap-8"
    >
      <div className="min-w-0 space-y-6">
        <EditionHero edition={edition} archived={archived} />
        {edition.sections.map((section) => (
          <motion.section
            key={section.profile}
            variants={listStagger}
            id={`section-${section.profile}`}
            aria-labelledby={`heading-${section.profile}`}
            className="scroll-mt-28 space-y-4"
          >
            <motion.h2
              variants={riseIn}
              id={`heading-${section.profile}`}
              className="flex items-center gap-3 px-1 pt-4 text-[13px] font-bold uppercase tracking-[0.1em] text-muted"
            >
              {section.name}
              <span className="h-px flex-1 bg-ink/10" />
              <span className="tabular-nums text-faint">{section.items.length}</span>
            </motion.h2>
            {section.items.map((item) => (
              <ItemCard key={item.id} item={item} editionId={edition.id} />
            ))}
          </motion.section>
        ))}
        {edition.unanalyzed.length > 0 && <UnanalyzedSection items={edition.unanalyzed} editionId={edition.id} />}
      </div>
      <EditionSidebar edition={edition} />
    </motion.div>
  )
}

function EditionSkeleton() {
  const { t } = useLanguage()
  return (
    <div role="status" aria-live="polite" className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px] xl:gap-8">
      <span className="sr-only">{t('state.loading')}</span>
      <div className="space-y-6">
        <div className="h-52 animate-shimmer rounded-card bg-accent/15" />
        {[0, 1, 2].map((index) => (
          <div key={index} className="h-60 animate-shimmer rounded-card bg-white/80 shadow-card" />
        ))}
      </div>
      <div className="hidden h-96 animate-shimmer rounded-card bg-white/50 xl:block" />
    </div>
  )
}
