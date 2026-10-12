import { ChartColumn, Table2 } from 'lucide-react'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from 'recharts'
import { Segmented } from '../../design/PageState'
import type { Run } from '../../lib/api'
import { formatShortDate, formatTime } from '../../lib/format'
import { useLanguage } from '../../lib/i18n'
import { useMotionPreference } from '../../lib/motion'

const COLLECTED = 'var(--color-series-collected)'
const SELECTED = 'var(--color-series-selected)'

type Point = { id: string; label: string; collected: number; selected: number }

/** Items collected vs selected per run: grouped columns, one shared axis, with a table view. */
export function RunVolumeChart({ runs }: { runs: Run[] }) {
  const { language, t } = useLanguage()
  const { enabled } = useMotionPreference()
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const data: Point[] = runs.map((run) => ({
    id: run.id,
    label: `${formatShortDate(run.started_at, language)} ${formatTime(run.started_at, language)}`,
    collected: run.fetched_count,
    selected: run.selected_count,
  }))

  return (
    <section aria-labelledby="volume-title" className="rounded-card bg-surface p-5 shadow-card sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="volume-title" className="text-[17px] font-bold">
            {t('sources.volume')}
          </h2>
          <p className="mt-1 text-[13.5px] text-muted">{t('sources.volumeHint')}</p>
        </div>
        <Segmented
          id="volume-view"
          label={t('sources.volume')}
          value={view}
          onChange={setView}
          options={[
            {
              value: 'chart',
              label: (
                <>
                  <ChartColumn size={14} aria-hidden />
                  {t('sources.showChart')}
                </>
              ),
            },
            {
              value: 'table',
              label: (
                <>
                  <Table2 size={14} aria-hidden />
                  {t('sources.showTable')}
                </>
              ),
            },
          ]}
        />
      </div>

      {data.length === 0 ? (
        <p className="mt-6 text-[14px] text-muted">{t('sources.noRuns')}</p>
      ) : view === 'chart' ? (
        <>
          <ul className="mt-5 flex gap-5 text-[13px] text-ink/80" aria-label="Legend">
            <LegendKey color={COLLECTED} label={t('sources.collected')} />
            <LegendKey color={SELECTED} label={t('sources.selected')} />
          </ul>
          <div className="mt-3 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} barGap={2} barCategoryGap="28%" margin={{ top: 8, right: 4, bottom: 0, left: -18 }}>
                <CartesianGrid vertical={false} stroke="var(--color-line)" />
                <XAxis
                  dataKey="label"
                  tickLine={false}
                  axisLine={{ stroke: 'var(--color-line)' }}
                  tick={{ fill: 'var(--color-faint)', fontSize: 11 }}
                  interval="preserveStartEnd"
                  minTickGap={16}
                />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: 'var(--color-faint)', fontSize: 11 }} />
                <Tooltip cursor={{ fill: 'rgb(15 21 48 / 0.04)' }} content={(props) => <VolumeTooltip {...props} />} />
                <Bar dataKey="collected" name={t('sources.collected')} fill={COLLECTED} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={enabled} />
                <Bar dataKey="selected" name={t('sources.selected')} fill={SELECTED} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={enabled} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-[14px]">
            <thead>
              <tr className="border-b border-line text-left text-[12px] font-semibold text-faint">
                <th className="py-2.5 pr-4 font-semibold">{t('sources.run')}</th>
                <th className="py-2.5 pr-4 text-right font-semibold">{t('sources.collected')}</th>
                <th className="py-2.5 text-right font-semibold">{t('sources.selected')}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((point) => (
                <tr key={point.id} className="border-b border-line/70 last:border-0">
                  <td className="py-2.5 pr-4">{point.label}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{point.collected}</td>
                  <td className="py-2.5 text-right tabular-nums">{point.selected}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function LegendKey({ color, label }: { color: string; label: string }) {
  return (
    <li className="flex items-center gap-2">
      <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: color }} aria-hidden />
      {label}
    </li>
  )
}

function VolumeTooltip({ active, payload, label }: TooltipContentProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="glass rounded-control px-3.5 py-2.5 text-[13px]">
      <p className="font-semibold">{label}</p>
      {payload.map((entry) => (
        <p key={String(entry.dataKey)} className="mt-1 flex items-center gap-2 text-ink/80">
          <span className="h-2 w-2 rounded-[2px]" style={{ background: entry.color }} aria-hidden />
          {entry.name}
          <span className="ml-auto pl-4 font-semibold tabular-nums text-ink">{entry.value}</span>
        </p>
      ))}
    </div>
  )
}
