import { fireEvent, screen, within } from '@testing-library/react'
import { fixtures, mockApi, renderAt } from '../../test/render'

const withProblems = {
  ...fixtures.sources,
  sources: [
    {
      ...fixtures.sources.sources[0],
      source: 'rss/Broken Feed',
      type: 'rss',
      status: 'dead',
      runs: 3,
      failures: 3,
      consecutive_failures: 3,
      items: 0,
      selected: 0,
      selection_rate: 0,
      last_success_at: null,
      last_error: "HTTPStatusError: Client error '404 Not Found'",
    },
    ...fixtures.sources.sources,
  ],
}

test('summarises health, charts runs and filters sources', async () => {
  const fetchMock = mockApi({ sources: withProblems })
  renderAt('/sources?lang=fr')

  expect(await screen.findByRole('heading', { level: 1, name: 'Santé des sources' })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/api/sources?days=14', expect.anything())
  expect(screen.getByText('Sources suivies').nextElementSibling).toHaveTextContent('30')
  expect(screen.getByText('En échec', { selector: 'dt' }).nextElementSibling).toHaveTextContent('1')

  // Localized reason and raw error for the dead source.
  const table = screen.getByRole('table')
  const row = within(table).getByText('Broken Feed').closest('tr')!
  expect(row).toHaveTextContent('Morte')
  expect(row).toHaveTextContent('échec aux 3 derniers runs')
  expect(row).toHaveTextContent('404 Not Found')

  fireEvent.click(screen.getByRole('button', { name: 'Morte · 1' }))
  expect(within(table).getAllByRole('row')).toHaveLength(2) // header + one source

  // Chart has a table view with the same numbers.
  fireEvent.click(screen.getByRole('button', { name: /Tableau/ }))
  const volume = screen.getByRole('region', { name: 'Volume par run' })
  expect(within(volume).getAllByRole('row')).toHaveLength(fixtures.sources.runs.length + 1)

  fireEvent.click(screen.getByRole('button', { name: '30 jours' }))
  expect(fetchMock).toHaveBeenCalledWith('/api/sources?days=30', expect.anything())
})
