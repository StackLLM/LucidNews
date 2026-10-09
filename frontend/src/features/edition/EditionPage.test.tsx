import { fireEvent, screen, within } from '@testing-library/react'
import { fixtures, mockApi, renderAt } from '../../test/render'

test('renders the edition with sections, figures and reliability labels', async () => {
  const fetchMock = mockApi()
  renderAt('/?lang=fr')

  expect(await screen.findByRole('heading', { level: 1, name: /6 octobre 2026/i })).toBeInTheDocument()
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
  fireEvent.click(within(first).getByRole('button', { name: /read more/i }))
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
