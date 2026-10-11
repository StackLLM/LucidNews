import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { fixtures, renderAt } from '../../test/render'
import sourceConfig from '../../test/fixtures/source-config.json'

type Call = { method: string; path: string; body: unknown }
type Reply = [number, unknown]

const testResult = {
  ok: true,
  count: 12,
  in_window: 3,
  window_hours: 24,
  days: 7,
  error: null,
  warnings: [],
  duration_ms: 812,
  sample: [{ title: 'Introducing a new model', url: 'https://openai.com/news/new-model', published_at: '2026-10-09T08:00:00+00:00' }],
}

// Real output of the API on config.example.json, health from the local archive.
const domains = {
  'rss/OpenAI News': { category: 'ai', origin: 'archive', categories: [{ category: 'ai', items: 12 }, { category: 'web', items: 2 }] },
  'rss/AWS News Blog': { category: 'cloud', origin: 'catalog', categories: [] },
  hackernews: { category: 'software-development', origin: 'archive', categories: [{ category: 'software-development', items: 1 }] },
}

function mockSourcesApi(write: (call: Call) => Reply = () => [200, { ...sourceConfig, version: 'v2' }], withDomains = false) {
  const calls: Call[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = decodeURIComponent(new URL(String(input), 'http://localhost').pathname)
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    const reply = ([status, payload]: Reply) => new Response(JSON.stringify(payload), { status })
    if (path === '/api/sources') return reply([200, fixtures.sources])
    if (path === '/api/sources/config' && method === 'GET') return reply([200, sourceConfig])
    if (path === '/api/sources/domains') return withDomains ? reply([200, { days: 90, domains }]) : reply([403, { error: 'off' }])
    if (path === '/api/sources/test') return reply([200, testResult])
    return reply(write({ method, path, body }))
  })
  return calls
}

async function openSources() {
  renderAt('/sources?lang=fr')
  return screen.findByRole('region', { name: 'Sources configurées' }, { timeout: 5000 })
}

function row(region: HTMLElement, name: string) {
  return within(region).getByText(name, { selector: 'p' }).closest('li')!
}

test('lists every configured source with its real state', async () => {
  mockSourcesApi()
  const region = await openSources()

  expect(row(region, 'Hacker News')).toHaveTextContent('Saine') // from past runs
  expect(row(region, 'OpenAI News')).toHaveTextContent('Pas encore collectée') // no run has seen it
  expect(row(region, 'r/LocalLLaMA')).toHaveTextContent('En pause')
  expect(row(region, 'r/LocalLLaMA')).toHaveTextContent('Reddit est désactivé')
  expect(row(region, 'GDELT')).toHaveTextContent('Désactivée')
  const x = row(region, 'X (Twitter)')
  expect(x).toHaveTextContent('Lecture seule')
  expect(x).toHaveTextContent('Mode apify · 2 comptes · 0 mots-clés')
  expect(within(x).queryByRole('switch')).toBeNull()
  expect(within(x).queryByRole('button', { name: /Gérer/ })).toBeNull()
  // The read-only banner is replaced by the per-source state.
  expect(screen.queryByText(/Configurées mais jamais collectées/)).toBeNull()
})

test('a switch enables or disables a source with the version that was read', async () => {
  const calls = mockSourcesApi()
  const region = await openSources()

  fireEvent.click(within(row(region, 'OpenAI News')).getByRole('switch', { name: 'Collecter OpenAI News' }))

  expect(await within(region).findByText('Enregistré. Appliqué dès le prochain run.')).toBeInTheDocument()
  expect(calls.find((call) => call.method === 'PUT')).toEqual({
    method: 'PUT',
    path: '/api/sources/config/rss/OpenAI News',
    body: { version: sourceConfig.version, values: { enabled: false } },
  })
})

test('adds a source after choosing its type', async () => {
  const calls = mockSourcesApi(() => [201, { ...sourceConfig, version: 'v2', key: 'reddit/r/rust' }])
  await openSources()

  fireEvent.click(screen.getByRole('button', { name: 'Ajouter une source' }))
  const panel = await screen.findByRole('dialog')
  fireEvent.change(within(panel).getByLabelText('Type'), { target: { value: 'reddit_subreddit' } })
  fireEvent.click(within(panel).getByRole('button', { name: 'Ajouter' }))
  expect(await within(panel).findByText('Obligatoire.')).toBeInTheDocument() // nothing sent yet
  expect(calls.some((call) => call.method === 'POST')).toBe(false)

  fireEvent.change(within(panel).getByLabelText('Subreddit'), { target: { value: 'r/rust' } })
  fireEvent.click(within(panel).getByRole('button', { name: 'Ajouter' }))

  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(calls.find((call) => call.method === 'POST')?.body).toEqual({
    version: sourceConfig.version,
    kind: 'reddit_subreddit',
    values: { subreddit: 'r/rust' },
  })
})

test('a refused address is shown on its field', async () => {
  mockSourcesApi(() => [422, { error: 'invalid source', fields: { url: 'Destination resolves to a non-public address: 10.0.0.1' } }])
  await openSources()

  fireEvent.click(screen.getByRole('button', { name: 'Ajouter une source' }))
  const panel = await screen.findByRole('dialog')
  fireEvent.change(within(panel).getByLabelText('Nom'), { target: { value: 'Intranet' } })
  fireEvent.change(within(panel).getByLabelText('Adresse du flux'), { target: { value: 'http://10.0.0.1/rss' } })
  fireEvent.click(within(panel).getByRole('button', { name: 'Ajouter' }))

  expect(
    await within(panel).findByText('Refusé par le serveur : Destination resolves to a non-public address: 10.0.0.1'),
  ).toBeInTheDocument()
  expect(within(panel).getByLabelText('Adresse du flux')).toHaveAttribute('aria-invalid', 'true')
})

test('a saved source is tested by key and the result is shown', async () => {
  const calls = mockSourcesApi()
  const region = await openSources()

  fireEvent.click(within(row(region, 'OpenAI News')).getAllByRole('button', { name: /Gérer/ })[0])
  const panel = await screen.findByRole('dialog')
  fireEvent.click(within(panel).getByRole('button', { name: 'Tester' }))

  expect(
    await within(panel).findByText('12 contenus sur 7 jours, dont 3 dans la fenêtre de collecte (24 h).'),
  ).toBeInTheDocument()
  expect(within(panel).getByRole('link', { name: 'Introducing a new model' })).toHaveAttribute('href', testResult.sample[0].url)
  expect(calls.find((call) => call.path === '/api/sources/test')?.body).toEqual({ key: 'rss/OpenAI News' })
  expect(calls.some((call) => call.method === 'PUT')).toBe(false) // a test writes nothing
})

test('an edited draft is tested with its values, then only changed fields are saved', async () => {
  const calls = mockSourcesApi()
  const region = await openSources()

  fireEvent.click(within(row(region, 'Hacker News')).getAllByRole('button', { name: /Gérer/ })[0])
  const panel = await screen.findByRole('dialog')
  fireEvent.change(within(panel).getByLabelText('Score minimal'), { target: { value: '150' } })
  fireEvent.click(within(panel).getByRole('button', { name: 'Tester' }))
  await within(panel).findByText(/12 contenus/)
  expect(calls.find((call) => call.path === '/api/sources/test')?.body).toEqual({
    kind: 'hackernews',
    values: { fetch_top_stories: 30, min_score: 150 },
  })

  fireEvent.click(within(panel).getByRole('button', { name: 'Enregistrer' }))
  await waitFor(() => expect(calls.find((call) => call.method === 'PUT')).toBeDefined())
  expect(calls.find((call) => call.method === 'PUT')?.body).toEqual({
    version: sourceConfig.version,
    values: { min_score: 150 },
  })
})

test('a source is deleted after confirmation', async () => {
  const calls = mockSourcesApi()
  const region = await openSources()

  fireEvent.click(within(row(region, 'OpenAI News')).getAllByRole('button', { name: /Gérer/ })[0])
  const panel = await screen.findByRole('dialog')
  fireEvent.click(within(panel).getByRole('button', { name: 'Supprimer' }))
  const confirm = await screen.findByRole('alertdialog')
  expect(confirm).toHaveTextContent('Supprimer OpenAI News ?')
  fireEvent.click(within(confirm).getByRole('button', { name: 'Supprimer' }))

  await waitFor(() => expect(calls.find((call) => call.method === 'DELETE')).toBeDefined())
  expect(calls.find((call) => call.method === 'DELETE')).toEqual({
    method: 'DELETE',
    path: '/api/sources/config/rss/OpenAI News',
    body: { version: sourceConfig.version },
  })
})

test('a configuration changed elsewhere asks to reload', async () => {
  mockSourcesApi(() => [409, { error: 'the configuration changed since it was read' }])
  const region = await openSources()

  fireEvent.click(within(row(region, 'Hacker News')).getAllByRole('button', { name: /Gérer/ })[0])
  const panel = await screen.findByRole('dialog')
  fireEvent.change(within(panel).getByLabelText('Score minimal'), { target: { value: '120' } })
  fireEvent.click(within(panel).getByRole('button', { name: 'Enregistrer' }))

  expect(await within(panel).findByText('La configuration a changé ailleurs. Rechargez, puis réessayez.')).toBeInTheDocument()
  expect(within(panel).getByRole('button', { name: 'Recharger' })).toBeInTheDocument()
})

test('groups the sources by domain and says where each domain comes from', async () => {
  mockSourcesApi(undefined, true)
  const region = await openSources()

  const ai = await within(region).findByRole('region', { name: /IA \/ LLM \/ Agents/ })
  expect(within(ai).getByText('OpenAI News')).toBeInTheDocument()
  expect(row(region, 'OpenAI News')).toHaveTextContent('Domaine : IA / LLM / Agents')
  expect(row(region, 'OpenAI News')).toHaveTextContent('d’après 14 news analysées')
  expect(row(region, 'OpenAI News')).toHaveTextContent('aussi : Web')
  // A source with no analyzed news yet gets the catalog's domain, and says so.
  const cloud = within(region).getByRole('region', { name: /Cloud/ })
  expect(within(cloud).getByText('AWS News Blog')).toBeInTheDocument()
  expect(row(region, 'AWS News Blog')).toHaveTextContent('selon le catalogue')
  // The others are not given a domain by guesswork.
  const unknown = within(region).getByRole('region', { name: /Domaine pas encore déterminé/ })
  expect(within(unknown).getByText('Google DeepMind')).toBeInTheDocument()
  expect(row(region, 'Google DeepMind')).toHaveTextContent('Domaine : pas encore déterminé')
  // The Reddit and Telegram switches are still there.
  expect(within(region).getByRole('region', { name: /Interrupteurs et sources spéciales/ })).toBeInTheDocument()
  expect(within(region).getAllByRole('switch', { name: /Reddit/ }).length).toBeGreaterThan(0)

  fireEvent.click(within(region).getByRole('button', { name: 'Type' }))
  expect(await within(region).findByRole('heading', { level: 3, name: /Flux RSS/ })).toBeInTheDocument()
  expect(row(region, 'OpenAI News')).toHaveTextContent('Domaine : IA / LLM / Agents') // still shown in the type view
})
