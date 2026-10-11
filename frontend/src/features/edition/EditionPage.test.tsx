import { fireEvent, screen, within } from '@testing-library/react'
import { fixtures, mockApi, renderAt } from '../../test/render'

test('renders the edition with sections, figures and reliability labels', async () => {
  const fetchMock = mockApi()
  renderAt('/?lang=fr')

  expect(await screen.findByRole('heading', { level: 1, name: /6 octobre 2026/i }, { timeout: 5000 })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/api/editions/latest?lang=fr', expect.anything())

  const index = screen.getByRole('navigation', { name: 'Dans cette édition' })
  expect(within(index).getAllByRole('link').map((link) => link.textContent)).toEqual([
    'Actualités tech6',
    'Blogs techniques3',
    'Radar créateurs IA4',
  ])
  expect(screen.getAllByRole('article')).toHaveLength(13)
  expect(screen.getByRole('link', { name: 'Sortie officielle de Polars 2.0' })).toHaveAttribute(
    'href',
    'https://pola.rs/posts/release-polars-2/',
  )
  // Unconfirmed items carry an explicit warning, never a bare fact.
  expect(screen.getAllByText('Pas confirmé par une source officielle ou reconnue.').length).toBeGreaterThanOrEqual(2)
})

test('switches language and expands an item', async () => {
  mockApi()
  renderAt('/?lang=fr')
  await screen.findByRole('heading', { level: 1 })

  fireEvent.click(screen.getByRole('button', { name: 'en' }))
  expect(await screen.findByRole('heading', { level: 1, name: /6 October 2026/i })).toBeInTheDocument()
  expect(document.documentElement.lang).toBe('en')
  await screen.findByRole('link', { name: /Polars 2.0 Released/ })

  const first = screen.getAllByRole('article')[0]
  fireEvent.click(within(first).getByRole('button', { name: /details/i }))
  expect(within(first).getByRole('button', { name: /show less/i })).toHaveAttribute('aria-expanded', 'true')
  expect(within(first).getByRole('heading', { level: 4, name: 'Background' })).toBeInTheDocument()
})

test('explains how to start the API when it is down', async () => {
  mockApi({}, 502)
  renderAt('/?lang=en')

  expect(await screen.findByRole('alert')).toHaveTextContent('uv run lucidnews-api')
})

test('lists items the AI could not analyze apart, only when the quota ran out', async () => {
  const base = fixtures.editionFr
  const raw = {
    ...base.sections[0].items[0],
    id: 'rss:test:raw',
    title: 'Titre brut non analysé',
    score: null,
    importance: null,
    summary: '',
    sections: [],
    categories: [],
    translated: false,
    ai_skipped: true,
    reliability: { ...base.sections[0].items[0].reliability, label: 'unverified' },
  }
  mockApi({
    edition: { ...base, selected_count: base.selected_count + 1, ai_limit: 'provider_quota', unanalyzed: [raw] },
  })
  renderAt('/?lang=fr')

  expect(await screen.findByText(/Le quota IA a été épuisé pendant ce run\./)).toHaveTextContent(
    '1 news est listée sans analyse, en fin d’édition.',
  )
  const section = screen.getByRole('region', { name: /Sans analyse IA/ })
  expect(within(section).getByRole('link', { name: 'Titre brut non analysé' })).toBeInTheDocument()
  expect(within(section).getByText(/ni résumé, ni score, ni vérification/)).toBeInTheDocument()
  expect(within(section).queryByText('/10')).toBeNull()
  // The 13 analyzed items stay in their sections; the raw one is not an article card.
  expect(screen.getAllByRole('article')).toHaveLength(13)
  expect(screen.getAllByText('contenus collectés').length).toBeGreaterThan(0)
  const index = screen.getByRole('navigation', { name: 'Dans cette édition' })
  expect(within(index).getByRole('link', { name: 'Sans analyse IA1' })).toHaveAttribute('href', '#section-unanalyzed')
})

test('shows no quota notice on a normal edition', async () => {
  mockApi()
  renderAt('/?lang=fr')
  await screen.findByRole('heading', { level: 1 })

  expect(screen.queryByText(/quota IA/)).toBeNull()
  expect(screen.queryByRole('region', { name: /Sans analyse IA/ })).toBeNull()
})

// --- Date filter ---------------------------------------------------------------------------

function mockPeriodApi(period: Record<string, unknown> = {}) {
  const spy = mockApi()
  const inner = spy.getMockImplementation()!
  spy.mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/editions/period') {
      return new Response(
        JSON.stringify({ ...fixtures.editionFr, id: 'period', edition_count: 8, analyzed_total: 13, listed_limit: 100, ...period }),
      )
    }
    return inner(input, init)
  })
  return spy
}

const periodCalls = (spy: ReturnType<typeof mockApi>) =>
  spy.mock.calls.map((call) => new URL(String(call[0]), 'http://localhost')).filter((url) => url.pathname === '/api/editions/period')

test('filters the news by month: all editions of the month, in one page', async () => {
  const spy = mockPeriodApi()
  renderAt('/?lang=fr')
  const filter = await screen.findByRole('region', { name: 'Filtrer par date' })
  expect(periodCalls(spy)).toHaveLength(0) // nothing is requested until a period is chosen

  fireEvent.click(within(filter).getByRole('button', { name: 'Mois' }))

  expect(await screen.findByRole('heading', { level: 1, name: 'Octobre 2026' })).toBeInTheDocument()
  expect(window.location.search).toContain('month=2026-10')
  expect(screen.getByText('8 éditions · 13 news')).toBeInTheDocument()
  const [call] = periodCalls(spy)
  // Local month boundaries, sent as instants.
  expect(new Date(call.searchParams.get('since')!).getTime()).toBe(new Date(2026, 9, 1).getTime())
  expect(new Date(call.searchParams.get('until')!).getTime()).toBe(new Date(2026, 10, 1).getTime())
  expect(screen.getAllByRole('article')).toHaveLength(13)
  // Items of a period do not link to a single edition.
  expect(screen.getAllByRole('link', { name: /Détails|Ouvrir/i }).every((link) => !link.getAttribute('href')?.includes('edition='))).toBe(true)
})

test('filters by year and by day, and goes back to the latest edition', async () => {
  const spy = mockPeriodApi()
  renderAt('/?lang=fr')
  const filter = await screen.findByRole('region', { name: 'Filtrer par date' })

  fireEvent.click(within(filter).getByRole('button', { name: 'Année' }))
  expect(await screen.findByRole('heading', { level: 1, name: '2026' })).toBeInTheDocument()
  expect(within(filter).getByRole('combobox', { name: 'Année' })).toHaveValue('2026')

  fireEvent.click(within(filter).getByRole('button', { name: 'Jour' }))
  expect(await screen.findByRole('heading', { level: 1, name: /Mardi 6 octobre 2026/i })).toBeInTheDocument()
  expect(window.location.search).toContain('day=2026-10-06')
  expect(window.location.search).not.toContain('year=')
  const last = periodCalls(spy).at(-1)!
  expect(new Date(last.searchParams.get('until')!).getTime() - new Date(last.searchParams.get('since')!).getTime()).toBeGreaterThan(0)

  fireEvent.click(within(filter).getByRole('button', { name: 'Dernière édition' }))
  expect(await screen.findByText(/Édition du jour/)).toBeInTheDocument()
  expect(window.location.search).not.toMatch(/day=|month=|year=/)
})

test('says when a period lists only the best news of many', async () => {
  mockPeriodApi({ analyzed_total: 480, listed_limit: 100 })
  renderAt('/?lang=fr&year=2026')

  expect(await screen.findByText(/Les 100 news les mieux notées sur 480 sont affichées/)).toBeInTheDocument()
})

test('a period without any edition says so', async () => {
  mockPeriodApi({ edition_count: 0, selected_count: 0, sections: [], unanalyzed: [], analyzed_total: 0 })
  renderAt('/?lang=fr&month=2020-01')
  expect(await screen.findByText('Aucune édition n’a été publiée sur cette période.')).toBeInTheDocument()
})

test('a malformed period in the address is ignored', async () => {
  const spy = mockPeriodApi()
  renderAt('/?lang=fr&month=2026-13')
  expect(await screen.findByRole('heading', { level: 1, name: /6 octobre 2026/i })).toBeInTheDocument()
  expect(periodCalls(spy)).toHaveLength(0)
})
