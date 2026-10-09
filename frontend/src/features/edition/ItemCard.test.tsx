import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { fixtures, mockApi, renderAt } from '../../test/render'

const curl = fixtures.itemFr
const itemCalls = (fetchMock: ReturnType<typeof mockApi>) =>
  fetchMock.mock.calls.filter(([input]) => String(input).startsWith('/api/items/'))

async function curlCard() {
  renderAt('/?lang=fr')
  const title = await screen.findByRole('link', { name: curl.title })
  return title.closest('article')!
}

test('a click anywhere on the card opens its details, fetched once for this item', async () => {
  const fetchMock = mockApi()
  const card = await curlCard()
  const toggle = within(card).getByRole('button', { name: 'Détails' })
  expect(toggle).toHaveAttribute('aria-expanded', 'false')

  fireEvent.click(within(card).getByText(/./, { selector: 'p.font-serif' }))
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  expect(await within(card).findByText(curl.claim!.evidence)).toHaveAttribute('lang', 'en')
  expect(within(card).getByText('rapportée par un média crédible')).toBeInTheDocument()
  expect(within(card).getByText('#curl')).toBeInTheDocument()
  expect(within(card).getByRole('link', { name: /Lire l’article original/ })).toHaveAttribute('href', curl.url)
  expect(itemCalls(fetchMock).map(([input]) => input)).toEqual([`/api/items/${encodeURIComponent(curl.id)}?lang=fr`])

  fireEvent.click(toggle) // close, then reopen: served from the cache
  await waitFor(() => expect(toggle).toHaveAttribute('aria-expanded', 'false'))
  fireEvent.click(toggle)
  await within(card).findByText(curl.claim!.evidence)
  expect(itemCalls(fetchMock)).toHaveLength(1)
})

test('links keep their own behaviour and Escape closes the card', async () => {
  mockApi()
  const card = await curlCard()
  const toggle = within(card).getByRole('button', { name: 'Détails' })

  fireEvent.click(within(card).getByRole('link', { name: curl.title }))
  expect(toggle).toHaveAttribute('aria-expanded', 'false')

  fireEvent.click(toggle)
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  fireEvent.keyDown(card, { key: 'Escape' })
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  expect(toggle).toHaveFocus()
})

test('a failed load shows an error with retry, then the details', async () => {
  const fetchMock = mockApi()
  const ok = fetchMock.getMockImplementation()!
  let fail = true
  fetchMock.mockImplementation(async (input, init) =>
    fail && String(input).startsWith('/api/items/') ? new Response('{"error":"down"}', { status: 502 }) : ok(input, init),
  )
  const card = await curlCard()

  fireEvent.click(within(card).getByRole('button', { name: 'Détails' }))
  const alert = await within(card).findByRole('alert')
  expect(alert).toHaveTextContent('Impossible de charger les détails.')

  fail = false
  fireEvent.click(within(alert).getByRole('button', { name: 'Réessayer' }))
  expect(await within(card).findByText(curl.claim!.evidence)).toBeInTheDocument()
})

test('details of another item are never shown on this card', async () => {
  mockApi({ item: { ...curl, id: 'rss:other:1' } })
  const card = await curlCard()

  fireEvent.click(within(card).getByRole('button', { name: 'Détails' }))

  expect(await within(card).findByRole('alert')).toBeInTheDocument()
  expect(within(card).queryByText(curl.claim!.evidence)).toBeNull()
})

test('a card without AI summary says so', async () => {
  const edition = structuredClone(fixtures.editionFr)
  edition.sections[0].items[0].summary = ''
  mockApi({ edition })
  renderAt('/?lang=fr')

  expect(await screen.findByText('Pas encore de résumé IA pour cette news.')).toBeInTheDocument()
})
