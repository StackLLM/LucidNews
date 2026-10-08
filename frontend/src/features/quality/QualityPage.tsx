import { ListChecks, PenLine } from 'lucide-react'
import { motion } from 'motion/react'
import { useLocation, useNavigate } from 'react-router'
import { PageHeader, Segmented } from '../../design/PageState'
import { useLanguage } from '../../lib/i18n'
import { listStagger, riseIn, useMotionPreference } from '../../lib/motion'
import { AnnotateView } from './AnnotateView'
import { ResultsView } from './ResultsView'

type Tab = 'annotate' | 'results'

export function QualityPage() {
  const { language, t } = useLanguage()
  const { enabled } = useMotionPreference()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const tab: Tab = pathname.endsWith('/results') ? 'results' : 'annotate'

  return (
    <motion.div variants={listStagger} initial={enabled ? 'hidden' : false} animate="visible" className="space-y-8">
      <PageHeader
        title={t('quality.title')}
        subtitle={t('quality.subtitle')}
        actions={
          <Segmented<Tab>
            id="quality-tab"
            label={t('quality.title')}
            value={tab}
            onChange={(next) =>
              navigate({ pathname: next === 'results' ? '/quality/results' : '/quality', search: `?lang=${language}` })
            }
            options={[
              { value: 'annotate', label: <><PenLine size={14} aria-hidden />{t('quality.tabAnnotate')}</> },
              { value: 'results', label: <><ListChecks size={14} aria-hidden />{t('quality.tabResults')}</> },
            ]}
          />
        }
      />
      <motion.div variants={riseIn}>{tab === 'results' ? <ResultsView /> : <AnnotateView />}</motion.div>
    </motion.div>
  )
}
