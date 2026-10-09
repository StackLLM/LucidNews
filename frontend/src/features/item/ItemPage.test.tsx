import { fireEvent, screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import { fixtures, mockApi, renderAt } from '../../test/render'

const curl = fixtures.itemFr

test('opens the full brief from an edition card', async () => {
  const fetchMock = mockApi()
  renderAt('/?lang=fr')

  const card = (await screen.findByRole('link', { name: curl.title })).closest('article')!
  fireEvent.click(within(card).getByRole('link', { name: 'Fiche complète' }))

  expect(await screen.findByRole('heading', { level: 1, name: curl.title }, { timeout: 5000 })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith(`/api/items/${encodeURIComponent(curl.id)}?lang=fr`, expect.anything())
  expect(new URLSearchParams(window.location.search).get('from')).toBe(fixtures.editionFr.id)
  const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' })
  expect(within(breadcrumb).getByRole('link', { name: /Mardi 6 octobre 2026/ })).toHaveAttribute(
    'href',
    `/editions/${fixtures.editionFr.id}?lang=fr`,
  )
})

test('shows reliability details and never presents an unverified claim as fact', async () => {
  mockApi()
  renderAt(`/items/${encodeURIComponent(curl.id)}?lang=fr`)

  const panel = await screen.findByRole('region', { name: 'Fiabilité' }, { timeout: 5000 })
  expect(within(panel).getByText('Non vérifié')).toBeInTheDocument()
  expect(within(panel).getByText('mastodon.social')).toBeInTheDocument()
  expect(within(panel).getByText('source communautaire')).toBeInTheDocument()
  expect(within(panel).getByText('rapportée par un média crédible')).toBeInTheDocument()
  // Evidence is AI output in English, marked as such.
  expect(within(panel).getByText(curl.claim!.evidence)).toHaveAttribute('lang', 'en')
  // Warning right under the title.
  expect(screen.getAllByText('Pas confirmé par une source officielle ou reconnue.').length).toBeGreaterThanOrEqual(2)
  expect(screen.getByRole('link', { name: /Lire l’article original/ })).toHaveAttribute('href', curl.url)
})

test('copies a shareable link', async () => {
  mockApi()
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  renderAt(`/items/${encodeURIComponent(curl.id)}?lang=en`)

  fireEvent.click(await screen.findByRole('button', { name: 'Copy link' }, { timeout: 5000 }))
  expect(await screen.findByRole('status')).toHaveTextContent('Link copied')
  expect(writeText).toHaveBeenCalledWith(window.location.href)
})

test('explains a missing item', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{"error":"item not found"}', { status: 404 }))
  renderAt('/items/missing?lang=en')

  expect(await screen.findByRole('alert', {}, { timeout: 5000 })).toHaveTextContent('This item is not in the archive.')
})

test('an item the AI could not analyze says so instead of showing a summary', async () => {
  mockApi({
    item: {
      ...curl,
      score: null,
      importance: null,
      summary: '',
      sections: [],
      categories: [],
      tags: [],
      claim: null,
      ai_skipped: true,
    },
  })
  renderAt(`/items/${encodeURIComponent(curl.id)}?lang=fr`)

  expect(
    await screen.findByText(/Cette news n’a pas été analysée : le quota IA était épuisé\./, {}, { timeout: 5000 }),
  ).toBeInTheDocument()
  expect(screen.queryByText('Score')).toBeNull()
  // The label hint stays in the reliability panel only, not as a second warning under the title.
  expect(screen.getAllByText('Pas confirmé par une source officielle ou reconnue.')).toHaveLength(1)
})
