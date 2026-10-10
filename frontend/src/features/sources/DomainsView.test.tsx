import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { renderAt } from '../../test/render'
import catalog from '../../test/fixtures/catalog.json'
import coverage from '../../test/fixtures/coverage-30d.json'
import sourceConfig from '../../test/fixtures/source-config.json'
import settings from '../../test/fixtures/settings.json'

type Call = { method: string; path: string; body: unknown }

const testResult = {
  ok: true,
  count: 6,
  in_window: 1,
  window_hours: 24,
  days: 7,
  error: null,
  warnings: [],
  duration_ms: 420,
  sample: [],
}

// Coverage: real API output on the local archive (30 days). Catalog: real output on config.example.json.
function mockDomainsApi({ local = true }: { local?: boolean } = {}) {
  const calls: Call[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost')
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path: url.pathname + url.search, body })
    const reply = (status: number, payload: unknown) => new Response(JSON.stringify(payload), { status })
    if (url.pathname === '/api/coverage') return reply(200, coverage)
    if (url.pathname === '/api/catalog') return reply(200, catalog)
    if (url.pathname.startsWith('/api/sources/config') && !local) return reply(403, { error: 'local only' })
    if (url.pathname === '/api/sources/config' && method === 'GET') return reply(200, sourceConfig)
    if (url.pathname === '/api/sources/config' && method === 'POST') return reply(201, { ...sourceConfig, version: 'v2' })
    if (url.pathname === '/api/sources/test') return reply(200, testResult)
    if (url.pathname === '/api/settings' && method === 'PUT') return reply(200, settings)
    return reply(404, { error: 'not found' })
  })
  return calls
}

async function openDomains() {
  renderAt('/sources?tab=domains&lang=fr')
  return screen.findByText('IA / LLM / Agents', { selector: 'h3' }, { timeout: 5000 })
}

function card(name: string) {
  return screen.getByText(name, { selector: 'h3' }).closest('li')!
}

test('shows the coverage of each domain from the archive', async () => {
  const calls = mockDomainsApi()
  await openDomains()

  expect(screen.getByRole('heading', { level: 1, name: 'Sources' })).toBeInTheDocument()
  expect(calls.some((call) => call.path === '/api/coverage?days=14')).toBe(true)
  expect(screen.getByText('Domaines suivis').nextElementSibling).toHaveTextContent('12/12')
  expect(screen.getByText('Lacunes', { selector: 'dt' }).nextElementSibling).toHaveTextContent('5')

  const ai = card('IA / LLM / Agents')
  expect(ai).toHaveTextContent('Bien couvert')
  expect(ai).toHaveTextContent('14 news · 5 publiées · 7 sources actives')
  expect(ai).toHaveTextContent('64 % confirmées ou fiables')

  const databases = card('Bases de données')
  expect(databases).toHaveTextContent('Lacune')
  expect(databases).toHaveTextContent('Moins de 2 sources actives')
  expect(databases).toHaveTextContent('Moins de 3 news en 30 jours')
  expect(databases).toHaveTextContent('Aucune news dans ce domaine sur la période.')
  expect(databases).toHaveTextContent('Aucune autre source du catalogue pour ce domaine.')
})

test('following a domain and the publishing option are saved as settings', async () => {
  const calls = mockDomainsApi()
  await openDomains()

  fireEvent.click(within(card('Bases de données')).getByRole('switch', { name: 'Suivre Bases de données' }))
  await waitFor(() => expect(calls.some((call) => call.method === 'PUT')).toBe(true))
  const put = calls.find((call) => call.method === 'PUT')!
  expect(put.path).toBe('/api/settings')
  expect(put.body).toEqual({
    version: sourceConfig.version,
    values: { digest: { watched_categories: coverage.watched.filter((entry) => entry !== 'databases') } },
  })
  expect(await screen.findByText('Enregistré. Appliqué dès le prochain run.')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('switch', { name: 'Ne publier que les domaines suivis' }))
  await waitFor(() => expect(calls.filter((call) => call.method === 'PUT')).toHaveLength(2))
  expect(calls.filter((call) => call.method === 'PUT')[1].body).toEqual({
    version: sourceConfig.version,
    values: { digest: { only_watched_categories: true } },
  })
})

test('gap thresholds are saved only when valid and changed', async () => {
  const calls = mockDomainsApi()
  await openDomains()

  const save = screen.getByRole('button', { name: 'Enregistrer les seuils' })
  expect(save).toBeDisabled()
  fireEvent.change(screen.getByLabelText('News minimum sur la période'), { target: { value: '5' } })
  fireEvent.click(save)

  await waitFor(() => expect(calls.some((call) => call.method === 'PUT')).toBe(true))
  expect(calls.find((call) => call.method === 'PUT')!.body).toEqual({
    version: sourceConfig.version,
    values: { digest: { coverage_min_sources: 2, coverage_min_items: 5 } },
  })
})

test('a recommended source is tested, then added with the sources API', async () => {
  const calls = mockDomainsApi()
  await openDomains()

  const security = card('Cybersécurité')
  fireEvent.click(within(security).getByRole('button', { name: /1 source recommandée/ }))
  const entry = (await within(security).findByText('Schneier on Security')).closest('li')!
  expect(entry).toHaveTextContent('Recommandée · non configurée')
  const add = within(entry).getByRole('button', { name: 'Ajouter' })
  expect(add).toBeDisabled() // test first

  fireEvent.click(within(entry).getByRole('button', { name: 'Tester' }))
  expect(await within(entry).findByText(/6 contenus sur 7 jours/)).toBeInTheDocument()
  expect(calls.find((call) => call.path === '/api/sources/test')?.body).toEqual({
    kind: 'rss',
    values: { name: 'Schneier on Security', url: 'https://www.schneier.com/feed/atom/' },
  })
  fireEvent.click(add)

  expect(await screen.findByText('Schneier on Security ajoutée. Elle sera collectée au prochain run.')).toBeInTheDocument()
  expect(calls.find((call) => call.method === 'POST' && call.path === '/api/sources/config')?.body).toEqual({
    version: sourceConfig.version,
    kind: 'rss',
    values: { name: 'Schneier on Security', url: 'https://www.schneier.com/feed/atom/' },
  })
})

test('without the local API the coverage stays readable, nothing can be changed', async () => {
  mockDomainsApi({ local: false })
  await openDomains()

  expect(await screen.findByText(/ne fonctionnent qu’avec l’API locale/)).toBeInTheDocument()
  expect(screen.queryAllByRole('switch')).toHaveLength(0)
  const security = card('Cybersécurité')
  fireEvent.click(within(security).getByRole('button', { name: /1 source recommandée/ }))
  const entry = (await within(security).findByText('Schneier on Security')).closest('li')!
  expect(within(entry).queryByRole('button', { name: 'Ajouter' })).toBeNull()
})

test('the tab is kept in the address', async () => {
  mockDomainsApi()
  await openDomains()

  fireEvent.click(screen.getByRole('button', { name: 'Sources' }))
  await waitFor(() => expect(window.location.search).not.toContain('tab=domains'))
  expect(window.location.search).toContain('lang=fr')
})
