import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { renderAt } from '../../test/render'
import overview from '../../test/fixtures/quality-overview-30d.json'

// Real API output on the local archive (30 days): 8 runs recorded before the selection counters.
function mockOverview(data: unknown = overview) {
  const paths: string[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    paths.push(url.pathname + url.search)
    const body = url.pathname === '/api/quality/overview' ? data : { error: 'not found' }
    return new Response(JSON.stringify(body), { status: url.pathname === '/api/quality/overview' ? 200 : 404 })
  })
  return paths
}

async function openOverview() {
  renderAt('/quality?lang=fr')
  return screen.findByText('Couverture des domaines', {}, { timeout: 5000 })
}

function card(title: string) {
  return screen.getByRole('heading', { level: 3, name: title }).closest('section')!
}

test('shows the indicators of the archive, each with its source', async () => {
  const paths = mockOverview()
  await openOverview()

  expect(paths).toContain('/api/quality/overview?days=14')
  expect(screen.getByRole('button', { name: /Vue d’ensemble/ })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText('Lacunes', { selector: 'dt' }).nextElementSibling).toHaveTextContent('5/12')
  expect(screen.getByText('Sources actives', { selector: 'dt' }).nextElementSibling).toHaveTextContent('11/29')
  expect(screen.getByText('Âge médian', { selector: 'dt' }).nextElementSibling).toHaveTextContent('4,1 h')
  expect(screen.getByText('Confirmées ou fiables', { selector: 'dt' }).nextElementSibling).toHaveTextContent('93 %')

  expect(card('Couverture des domaines')).toHaveTextContent('5 sur 12 domaines suivis')
  expect(card('Couverture des domaines')).toHaveTextContent('Bases de données')
  expect(card('Diversité des sources')).toHaveTextContent('Première source des contenus collectés : Lobsters, 48 %.')
  expect(card('Santé des sources')).toHaveTextContent('Aucune erreur de collecte sur la période.')
  expect(card('Fraîcheur')).toHaveTextContent('médiane 4,1 h, 90 % sous 9,9 h')
  expect(card('Fiabilité des news publiées')).toHaveTextContent('Confirmé8')
  expect(card('Fraîcheur')).toHaveTextContent('Source : runs archivés, news archivées · 30 derniers jours')
})

test('runs recorded before the counters show no made-up number', async () => {
  mockOverview()
  await openOverview()

  const selection = card('Doublons et filtrage')
  expect(selection).toHaveTextContent('Aucun run de la période n’a encore enregistré ces compteurs. Ils commencent au prochain run.')
  expect(within(selection).queryByText('Fusionnés par URL')).toBeNull()
})

test('the funnel uses only the runs that recorded the counters', async () => {
  const withCounters = {
    ...overview,
    selection: {
      ...overview.selection,
      runs_with_data: 1,
      runs_without_data: 1,
      fetched: 40,
      url_merged: 3,
      topic_merged: 2,
      above_threshold: 9,
      per_run: [
        { ...overview.selection.per_run[0] },
        { run_id: 'new', started_at: '2026-10-11T08:00:00+00:00', fetched: 40, selected: 6, url_merged: 3, topic_merged: 2, above_threshold: 9 },
      ],
    },
  }
  mockOverview(withCounters)
  await openOverview()

  const selection = card('Doublons et filtrage')
  const numbers = Object.fromEntries(
    within(selection)
      .getAllByRole('term')
      .map((term) => [term.textContent, term.nextElementSibling?.textContent]),
  )
  expect(numbers).toEqual({ Collectés: '40', 'Fusionnés par URL': '3', 'Au-dessus du seuil': '9', 'Fusionnés par sujet': '2', Publiés: '6' })
  expect(selection).toHaveTextContent('1 run de la période a été enregistré avant ces compteurs : pas de donnée pour lui.')
})

test('filtering quality says when the sample is too small, or that it needs the local API', async () => {
  mockOverview({
    ...overview,
    filtering: { annotated: 4, compared: 4, small_sample: true, precision: 0.75, recall: 1, false_reliable: 1, min_sample: 30 },
  })
  await openOverview()

  const filtering = card('Qualité du filtrage')
  expect(filtering).toHaveTextContent('Échantillon insuffisant : 4 news annotées comparées, 30 nécessaires.')
  expect(filtering).toHaveTextContent('Précision75 %')
  expect(within(filtering).getByRole('link', { name: /Annoter/ })).toHaveAttribute('href', '/quality/annotate?lang=fr')
})

test('without the local API the evaluation is not shown', async () => {
  mockOverview({ ...overview, filtering: null })
  await openOverview()

  expect(card('Qualité du filtrage')).toHaveTextContent('Les annotations ne sont lues qu’avec l’API locale.')
})

test('the Annotate tab has its own address', async () => {
  mockOverview()
  await openOverview()

  fireEvent.click(screen.getByRole('button', { name: /Annoter/ }))
  await waitFor(() => expect(window.location.pathname).toBe('/quality/annotate'))
})
