import { fireEvent, screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import evalItems from '../../test/fixtures/eval-items.json'
import report from '../../test/fixtures/quality-report.synthetic.json'
import { renderAt } from '../../test/render'

// eval-items: 3 real archive items (blind payload). quality-report: computed by the
// backend on the synthetic items of tests/test_evaluation.py — not real results.

function fakeApi() {
  const items = structuredClone(evalItems.items) as { id: string; annotation: unknown }[]
  const calls: { method: string; path: string; body?: Record<string, unknown> }[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = decodeURIComponent(new URL(String(input), 'http://localhost').pathname)
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
    if (path === '/api/eval/items') return json({ items, annotated: items.filter((i) => i.annotation).length })
    if (path === '/api/eval/report') return json(report)
    const id = path.replace('/api/eval/annotations/', '')
    const item = items.find((entry) => entry.id === id)
    if (item && method === 'PUT') {
      item.annotation = { ...body, item_id: id, annotated_at: '2026-10-08T10:00:00+00:00' }
      return json(item.annotation)
    }
    return json({ error: 'not found' }, 404)
  })
  return calls
}

test('annotates blind and moves to the next item', async () => {
  const calls = fakeApi()
  renderAt('/quality/annotate?lang=fr')

  const first = evalItems.items[0]
  expect(await screen.findByRole('heading', { level: 2, name: first.title })).toBeInTheDocument()
  expect(screen.getByText('L’avis de l’IA est masqué ici, pour ne pas vous influencer.')).toBeInTheDocument()
  expect(screen.getByText('0 news annotées sur 3')).toBeInTheDocument()

  // Incomplete: nothing is sent.
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer et suivante' }))
  expect(screen.getByText('Répondez d’abord aux questions ci-dessus.')).toBeInTheDocument()

  fireEvent.click(within(screen.getByRole('group', { name: 'Cette news doit-elle figurer dans l’édition ?' })).getByRole('button', { name: 'Oui' }))
  fireEvent.click(screen.getByRole('button', { name: 'Élevée' }))
  for (const topic of ['Cybersécurité', 'Web', 'Cloud', 'DevOps']) fireEvent.click(screen.getByRole('button', { name: topic }))
  fireEvent.click(screen.getByRole('radio', { name: 'rapportée par un média crédible' }))
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer et suivante' }))

  expect(await screen.findByRole('heading', { level: 2, name: evalItems.items[1].title })).toBeInTheDocument()
  expect(calls.find((call) => call.method === 'PUT')).toEqual({
    method: 'PUT',
    path: `/api/eval/annotations/${first.id}`,
    body: {
      relevant: true,
      importance: 'high',
      claim_status: 'reported',
      categories: ['cybersecurity', 'web', 'cloud'], // capped at three
      notes: '',
    },
  })
  expect(await screen.findByText('1 news annotées sur 3')).toBeInTheDocument()
})

test('shows results with the false-reliable alert first', async () => {
  fakeApi()
  renderAt('/quality/results?lang=en')

  const tile = (await screen.findByText('False reliable')).closest('div')!
  expect(tile).toHaveTextContent('1')
  expect(screen.getByText(/Only 3 item\(s\) compared/)).toBeInTheDocument()

  const critical = screen.getByRole('region', { name: 'Most serious errors' })
  expect(within(critical).getByRole('link', { name: 'leak title' })).toBeInTheDocument()
  expect(within(critical).getByText('false reliable')).toBeInTheDocument()

  const selection = screen.getByRole('region', { name: 'Selection: you vs the pipeline' })
  expect(
    within(selection)
      .getAllByRole('cell')
      .map((cell) => cell.textContent),
  ).toEqual(['2', '1', '0', '0'])
})
