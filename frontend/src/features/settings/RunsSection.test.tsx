import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { renderAt } from '../../test/render'
import settingsFixture from '../../test/fixtures/settings.json'

type Call = { method: string; path: string; body: unknown }
const idle = { running: false, origin: null, started_at: null, step: null, steps: [], exit_code: null, already_running: false, log: '' }
const running = { ...idle, running: true, origin: 'web', started_at: '2026-10-11T07:00:00+00:00', step: 'analyze', log: 'Fetched 12 items from all sources' }
const history = [
  {
    id: '20261011T070000Z-aaaaaaaa',
    started_at: '2026-10-11T07:00:00+00:00',
    finished_at: '2026-10-11T07:04:00+00:00',
    fetched_count: 46,
    selected_count: 13,
    ai_limit: null,
    tokens_used: 0,
    ai_skipped_count: 0,
    status: 'success',
    error: null,
    unscored_count: 0,
  },
  {
    id: '20261010T070000Z-bbbbbbbb',
    started_at: '2026-10-10T07:00:00+00:00',
    finished_at: '2026-10-10T07:00:05+00:00',
    fetched_count: 0,
    selected_count: 0,
    ai_limit: null,
    tokens_used: 0,
    ai_skipped_count: 0,
    status: 'failed',
    error: 'All 3 attempted sources failed',
    unscored_count: 0,
  },
]

function mockRunsApi({
  current = [idle] as unknown[],
  start = [202, running] as [number, unknown],
  schedule = { supported: true, enabled: false, valid: true, loaded: false, hour: null, minute: null, weekdays: [], next_run: null } as unknown,
  saved = { supported: true, enabled: true, valid: true, loaded: true, hour: 6, minute: 45, weekdays: [1, 5], next_run: '2026-10-12T06:45+02:00' } as unknown,
} = {}) {
  const calls: Call[] = []
  let currentIndex = 0
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    const reply = (status: number, payload: unknown) => new Response(JSON.stringify(payload), { status })
    if (path === '/api/settings') return reply(200, settingsFixture)
    if (path === '/api/secrets') return reply(200, { secrets: [] })
    if (path === '/api/settings/backups') return reply(200, { backups: [] })
    if (path === '/api/runs/current') return reply(200, current[Math.min(currentIndex++, current.length - 1)])
    if (path === '/api/runs' && method === 'POST') return reply(...start)
    if (path === '/api/runs') return reply(200, { runs: history })
    if (path === '/api/schedule' && method === 'PUT') return reply(200, saved)
    if (path === '/api/schedule') return reply(200, schedule)
    return reply(404, { error: 'not found' })
  })
  return calls
}

async function openRuns() {
  renderAt('/settings?lang=fr')
  return screen.findByRole('region', { name: 'Runs' }, { timeout: 5000 })
}

test('a run is started and followed until it ends', async () => {
  const finished = { ...idle, origin: 'web', started_at: running.started_at, step: 'done', exit_code: 0, log: 'LucidNews completed successfully!' }
  const calls = mockRunsApi({ current: [idle, running, finished] })
  const runs = await openRuns()

  expect(await within(runs).findByText('Aucun run en cours.')).toBeInTheDocument()
  fireEvent.click(within(runs).getAllByRole('button', { name: 'Lancer un run' })[0])

  expect(await within(runs).findByText('Run en cours')).toBeInTheDocument()
  expect(within(runs).getByText(/lancé depuis cette page/)).toBeInTheDocument()
  expect(within(runs).getByText('Analyse IA').closest('li')).toHaveAttribute('aria-current', 'step')
  expect(within(runs).getAllByRole('button', { name: 'Lancer un run' })[0]).toBeDisabled()
  expect(calls.filter((call) => call.method === 'POST' && call.path === '/api/runs')).toHaveLength(1)

  // The page polls while the run is in progress.
  expect(await within(runs).findByText('Terminé. Le résultat est dans la liste ci-dessous.', {}, { timeout: 6000 })).toBeInTheDocument()
}, 10000)

test('a second run is refused while one is in progress', async () => {
  mockRunsApi({ current: [idle, running], start: [409, { error: 'a run is already in progress', ...running }] })
  const runs = await openRuns()

  await within(runs).findByText('Aucun run en cours.')
  fireEvent.click(within(runs).getAllByRole('button', { name: 'Lancer un run' })[0])

  expect(await within(runs).findByText('Un run est déjà en cours.')).toBeInTheDocument()
  expect(await within(runs).findByText('Run en cours')).toBeInTheDocument()
})

test('a failed run says so and opens its log', async () => {
  mockRunsApi({ current: [{ ...idle, origin: 'web', step: 'analyze', exit_code: 1, log: 'Fatal error: boom' }] })
  const runs = await openRuns()

  expect(await within(runs).findByText('Échec (code 1). Voir le journal.')).toBeInTheDocument()
  const log = within(runs).getByText('Fatal error: boom').closest('details')!
  expect(log).toHaveAttribute('open')
})

test('the schedule is saved with its time and days', async () => {
  const calls = mockRunsApi()
  const runs = await openRuns()
  const schedule = within(runs).getByRole('region', { name: 'Planification' })

  expect(await within(schedule).findByText('Non planifié.')).toBeInTheDocument()
  fireEvent.click(within(schedule).getByRole('switch'))
  fireEvent.change(within(schedule).getByLabelText('Heure'), { target: { value: '06:45' } })
  fireEvent.click(within(schedule).getByRole('button', { name: 'Lun' }))
  fireEvent.click(within(schedule).getByRole('button', { name: 'Ven' }))
  fireEvent.click(within(schedule).getByRole('button', { name: 'Enregistrer la planification' }))

  await waitFor(() => expect(calls.some((call) => call.method === 'PUT')).toBe(true))
  expect(calls.find((call) => call.method === 'PUT')?.body).toEqual({ enabled: true, hour: 6, minute: 45, weekdays: [1, 5] })
  expect(await within(schedule).findByText('Planification enregistrée.')).toBeInTheDocument()
  expect(within(schedule).getByText(/Prochain run : Lundi 12 octobre 2026/)).toBeInTheDocument()
})

test('scheduling is explained when it is not available', async () => {
  mockRunsApi({ schedule: { supported: false, enabled: false } })
  const runs = await openRuns()

  expect(await within(runs).findByText('La planification utilise launchd et n’existe que sur macOS.')).toBeInTheDocument()
})

test('recent runs show their real status', async () => {
  mockRunsApi()
  const runs = await openRuns()
  const list = within(runs).getByRole('region', { name: 'Runs récents' })

  expect(await within(list).findByText('Réussi')).toBeInTheDocument()
  expect(within(list).getByText('46 collectés · 13 publiés')).toBeInTheDocument()
  expect(within(list).getByRole('link', { name: 'Ouvrir l’édition' })).toHaveAttribute('href', `/editions/${history[0].id}?lang=fr`)
  expect(within(list).getByText('Échec')).toBeInTheDocument()
  expect(within(list).getByText('All 3 attempted sources failed')).toBeInTheDocument()
})
