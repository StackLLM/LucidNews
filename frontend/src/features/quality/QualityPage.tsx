import { LayoutDashboard, ListChecks, PenLine } from 'lucide-react'
import { m } from 'motion/react'
import { useLocation, useNavigate } from 'react-router'
import { PageHeader, Segmented } from '../../design/PageState'
import { useLanguage } from '../../lib/i18n'
import { listStagger, riseIn, useMotionPreference } from '../../lib/motion'
import { AnnotateView } from './AnnotateView'
import { OverviewView } from './OverviewView'
import { ResultsView } from './ResultsView'

type Tab = 'overview' | 'annotate' | 'results'
const PATHS: Record<Tab, string> = { overview: '/quality', annotate: '/quality/annotate', results: '/quality/results' }

export function QualityPage() {
  const { language, t } = useLanguage()
  const { enabled } = useMotionPreference()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const tab: Tab = pathname.endsWith('/results') ? 'results' : pathname.endsWith('/annotate') ? 'annotate' : 'overview'

  return (
    <m.div variants={listStagger} initial={enabled ? 'hidden' : false} animate="visible" className="space-y-8">
      <PageHeader
        title={t('quality.title')}
        subtitle={tab === 'overview' ? t('overview.subtitle') : t('quality.subtitle')}
        actions={
          <Segmented<Tab>
            id="quality-tab"
            label={t('quality.title')}
            value={tab}
            onChange={(next) => navigate({ pathname: PATHS[next], search: `?lang=${language}` })}
            options={[
              {
                value: 'overview',
                label: (
                  <>
                    <LayoutDashboard size={14} aria-hidden />
                    {t('quality.tabOverview')}
                  </>
                ),
              },
              {
                value: 'annotate',
                label: (
                  <>
                    <PenLine size={14} aria-hidden />
                    {t('quality.tabAnnotate')}
                  </>
                ),
              },
              {
                value: 'results',
                label: (
                  <>
                    <ListChecks size={14} aria-hidden />
                    {t('quality.tabResults')}
                  </>
                ),
              },
            ]}
          />
        }
      />
      <m.div variants={riseIn}>{tab === 'results' ? <ResultsView /> : tab === 'annotate' ? <AnnotateView /> : <OverviewView />}</m.div>
    </m.div>
  )
}
