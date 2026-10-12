import { render as renderNode, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { highlight } from '../../lib/highlight'
import { mockApi, renderAt } from '../../test/render'

const hit = (id: string, overrides: Record<string, unknown> = {}) => ({
  id,
  title: `Kubernetes ${id}`,
  summary: 'Le nouvel écosystème accélère les déploiements.',
  score: 8.5,
  reliability: 'confirmed',
  categories: ['cloud', 'devops'],
  source: 'rss/K8s Blog',
  source_type: 'rss',
  published_at: '2026-10-06T08:00:00+00:00',
  edition: 'run-1',
  edition_at: '2026-10-06T17:48:48+00:00',
  unanalyzed: false,
  ...overrides,
})

const payload = (overrides: Record<string, unknown> = {}) => ({
  query: 'kubernetes',
  terms: ['kubernetes'],
  total: 2,
  offset: 0,
  limit: 30,
  truncated: false,
  results: [hit('a'), hit('b', { edition: null, edition_at: null, reliability: 'rumor' })],
  facets: {
    categories: { cloud: 2, devops: 2 },
    labels: { confirmed: 1, rumor: 1 },
    sources: [{ source: 'rss/K8s Blog', count: 2 }],
  },
  ...overrides,
})

function mockSearch(reply: (url: URL) => [number, unknown]) {
  const spy = mockApi()
  const inner = spy.getMockImplementation()!
  const calls: URL[] = []
  spy.mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/search') {
      calls.push(url)
      const [status, body] = reply(url)
      return new Response(JSON.stringify(body), { status })
    }
    return inner(input, init)
  })
  return calls
}

async function search(text: string) {
  const field = await screen.findByRole('searchbox', { name: 'Rechercher dans l’archive' }, { timeout: 5000 })
  fireEvent.change(field, { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Rechercher' }))
}

test('searches the archive and shows each result with its context', async () => {
  const calls = mockSearch(() => [200, payload()])
  renderAt('/archive?lang=fr')

  await search('Kubernetes')

  expect(await screen.findByText('2 résultats pour « kubernetes »')).toBeInTheDocument()
  expect(window.location.search).toContain('q=Kubernetes')
  expect(calls[0].searchParams.get('q')).toBe('Kubernetes')
  expect(calls[0].searchParams.get('lang')).toBe('fr')
  const [published, unpublished] = screen.getAllByRole('link', { name: /Kubernetes/ })
  expect(published).toHaveAttribute('href', '/items/a?lang=fr&from=run-1')
  expect(within(published).getByText(/Publiée dans l’édition du .*6 octobre 2026/)).toBeInTheDocument()
  expect(unpublished).toHaveAttribute('href', '/items/b?lang=fr') // never published: no edition to go back to
  expect(within(unpublished).getByText('Analysée, non publiée dans une édition')).toBeInTheDocument()
  expect(within(unpublished).getByText('Rumeur')).toBeInTheDocument()
  expect(within(published).getByText('Kubernetes', { selector: 'mark' })).toBeInTheDocument()
  // The editions list gives way to the results.
  expect(screen.queryByRole('region', { name: 'Choisir un jour' })).not.toBeInTheDocument()
})

test('filters narrow the search from the first results, and show their counts', async () => {
  const calls = mockSearch(() => [200, payload()])
  renderAt('/archive?lang=fr&q=kubernetes&offset=30')

  const domain = await screen.findByRole('combobox', { name: 'Domaine' }, { timeout: 5000 })
  expect(within(domain).getByRole('option', { name: 'Cloud (2)' })).toBeInTheDocument()
  expect(within(domain).getByRole('option', { name: 'Bases de données (0)' })).toBeDisabled()
  expect(calls[0].searchParams.get('offset')).toBe('30')

  fireEvent.change(domain, { target: { value: 'devops' } })
  await waitFor(() => expect(calls.at(-1)!.searchParams.get('category')).toBe('devops'))
  expect(calls.at(-1)!.searchParams.get('offset')).toBeNull() // back to the first page
  fireEvent.change(screen.getByRole('combobox', { name: 'Fiabilité' }), { target: { value: 'rumor' } })
  await waitFor(() => expect(calls.at(-1)!.searchParams.get('label')).toBe('rumor'))
  fireEvent.change(screen.getByRole('combobox', { name: 'Source' }), { target: { value: 'rss/K8s Blog' } })
  await waitFor(() => expect(calls.at(-1)!.searchParams.get('source')).toBe('rss/K8s Blog'))
  expect(window.location.search).toMatch(/category=devops.*label=rumor.*source=/)
})

test('pages through many results', async () => {
  const calls = mockSearch((url) => [200, payload({ total: 65, offset: Number(url.searchParams.get('offset') ?? 0) })])
  renderAt('/archive?lang=fr&q=kubernetes')

  expect(await screen.findByText('1–2 sur 65', {}, { timeout: 5000 })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Précédent' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))

  await waitFor(() => expect(calls.at(-1)!.searchParams.get('offset')).toBe('30'))
  expect(await screen.findByText('31–32 sur 65')).toBeInTheDocument()
})

test('says so when nothing matches, and when the search is too big', async () => {
  mockSearch(() => [200, payload({ total: 0, results: [], truncated: true, facets: { categories: {}, labels: {}, sources: [] } })])
  renderAt('/archive?lang=fr&q=zzzz')

  expect(await screen.findByText(/Aucun résultat pour « kubernetes »/, {}, { timeout: 5000 })).toBeInTheDocument()
  expect(screen.getByText(/seules les meilleures sont prises en compte/)).toBeInTheDocument()
})

test('refuses an empty, too short or too long search without asking the API', async () => {
  const calls = mockSearch(() => [200, payload()])
  renderAt('/archive?lang=fr')

  await search('a')
  expect(await screen.findByText('Saisissez au moins un mot de 2 lettres.')).toBeInTheDocument()
  await search('x'.repeat(201))
  expect(await screen.findByText('La recherche est limitée à 200 caractères.')).toBeInTheDocument()
  await search('   ')
  expect(calls).toHaveLength(0)
  expect(window.location.search).not.toContain('q=')
})

test('explains an API refusal and an unavailable search', async () => {
  mockSearch(() => [503, { error: 'full-text search is not available' }])
  renderAt('/archive?lang=fr&q=kubernetes')
  expect(await screen.findByText('La recherche n’est pas disponible sur cette machine (SQLite sans FTS5).', {}, { timeout: 5000 })).toBeInTheDocument()
})

test('clearing the search brings back the editions', async () => {
  mockSearch(() => [200, payload()])
  renderAt('/archive?lang=fr&q=kubernetes&category=cloud')
  await screen.findByText('2 résultats pour « kubernetes »', {}, { timeout: 5000 })

  fireEvent.click(screen.getByRole('button', { name: 'Effacer la recherche' }))

  expect(await screen.findByRole('region', { name: 'Choisir un jour' })).toBeInTheDocument()
  expect(window.location.search).not.toMatch(/q=|category=/)
})

test('highlight marks word starts, ignoring case and accents, and never mid-word', () => {
  const { container } = renderNode(<p>{highlight('Un Écosystème de paquets, déjà là. Pré-requis', ['ecosysteme', 'pre', 'quet'])}</p>)

  expect([...container.querySelectorAll('mark')].map((mark) => mark.textContent)).toEqual(['Écosystème', 'Pré'])
  expect(container.textContent).toBe('Un Écosystème de paquets, déjà là. Pré-requis')
})
