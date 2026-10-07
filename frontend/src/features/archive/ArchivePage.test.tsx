import { fireEvent, screen, within } from '@testing-library/react'
import { fixtures, mockApi, renderAt } from '../../test/render'

test('lists editions by day and opens one', async () => {
  mockApi()
  renderAt('/archive?lang=fr')

  // First render loads the archive chunk (calendar), hence the longer wait.
  expect(await screen.findByRole('heading', { level: 1, name: 'Archives' }, { timeout: 5000 })).toBeInTheDocument()
  const links = screen.getAllByRole('link', { name: /retenus? sur/ })
  expect(links).toHaveLength(fixtures.editions.editions.length)
  expect(within(links[0]).getByText('13 retenus sur 46')).toBeInTheDocument()
  expect(within(links[1]).getByText('1 retenu sur 9')).toBeInTheDocument()

  fireEvent.click(links[0])
  expect(await screen.findByText('Édition archivée')).toBeInTheDocument()
  expect(window.location.pathname).toBe(`/editions/${fixtures.editions.editions[0].id}`)
})

test('filters the list with the calendar', async () => {
  mockApi()
  renderAt('/archive?lang=en')
  await screen.findByRole('heading', { level: 1, name: 'Archive' }, { timeout: 5000 })

  const calendar = screen.getByRole('region', { name: 'Pick a day' })
  const days = within(calendar).getAllByRole('button').filter((button) => !button.hasAttribute('disabled'))
  // Only days with an edition are selectable (plus the month navigation).
  expect(days.map((button) => button.getAttribute('aria-label'))).toEqual([
    'Go to the Previous Month',
    'Go to the Next Month',
    'Tuesday, 6 October 2026',
  ])
  fireEvent.click(days[2])

  expect(screen.getByRole('heading', { level: 2, name: /6 October 2026/ })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Show all' }))
  expect(screen.queryByRole('button', { name: 'Show all' })).not.toBeInTheDocument()
})
