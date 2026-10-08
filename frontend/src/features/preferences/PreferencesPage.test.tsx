import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import options from '../../test/fixtures/preference-options.json'
import { renderAt } from '../../test/render'

// In-memory stand-in for the local subscriber routes (fictitious addresses only).
type Stored = { id: string; email: string; plan: 'free'; preferences: Record<string, unknown>; created_at: string }

const basePreferences = {
  language: 'en',
  categories: [],
  sources: [],
  frequency: 'daily',
  min_importance: null,
  include_unconfirmed: true,
  max_items: null,
}

function fakeApi(initial: Stored[] = []) {
  const subscribers = [...initial]
  const calls: { method: string; path: string; body?: unknown }[] = []
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    if (path === '/api/preferences/options') return json(options)
    if (path === '/api/subscribers' && method === 'GET') return json({ subscribers })
    if (path === '/api/subscribers' && method === 'POST') {
      if (subscribers.some((s) => s.email === body.email)) return json({ error: 'exists', fields: { email: 'already subscribed' } }, 409)
      const created: Stored = {
        id: `id${subscribers.length.toString().padStart(14, '0')}`,
        email: body.email,
        plan: 'free',
        preferences: { ...basePreferences },
        created_at: '2026-10-08T09:00:00+00:00',
      }
      subscribers.push(created)
      return json(created, 201)
    }
    const match = path.match(/^\/api\/subscribers\/(\w+)$/)
    const index = subscribers.findIndex((s) => s.id === match?.[1])
    if (match && index >= 0 && method === 'PUT') {
      subscribers[index] = { ...subscribers[index], preferences: body.preferences }
      return json(subscribers[index])
    }
    if (match && index >= 0 && method === 'DELETE') {
      subscribers.splice(index, 1)
      return json({ deleted: match[1] })
    }
    return json({ error: 'not found' }, 404)
  })
  return { subscribers, calls }
}

const ada: Stored = {
  id: 'ada0000000000000',
  email: 'ada@example.com',
  plan: 'free',
  preferences: { ...basePreferences },
  created_at: '2026-10-01T09:00:00+00:00',
}

test('adds a subscriber and opens their preferences', async () => {
  const api = fakeApi()
  renderAt('/preferences?lang=fr')

  expect(await screen.findByText('Aucun abonné pour l’instant. Ajoutez le premier ci-dessous.', {}, { timeout: 5000 })).toBeInTheDocument()

  const input = screen.getByLabelText('Adresse e-mail')
  fireEvent.change(input, { target: { value: 'pas-un-email' } })
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }))
  expect(await screen.findByText('Saisissez une adresse e-mail valide.')).toBeInTheDocument()
  expect(api.calls.some((call) => call.method === 'POST')).toBe(false)

  fireEvent.change(input, { target: { value: 'grace@example.com' } })
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }))

  expect(await screen.findByRole('heading', { level: 2, name: 'grace@example.com' })).toBeInTheDocument()
  expect(window.location.pathname).toBe(`/preferences/${api.subscribers[0].id}`)
})

test('edits and saves preferences', async () => {
  const api = fakeApi([ada])
  renderAt(`/preferences/${ada.id}?lang=fr`)

  await screen.findByRole('heading', { level: 2, name: 'ada@example.com' }, { timeout: 5000 })
  expect(screen.queryByRole('button', { name: 'Enregistrer' })).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Français' }))
  fireEvent.click(screen.getByRole('button', { name: 'Cybersécurité' }))
  fireEvent.click(screen.getByRole('button', { name: 'Web' }))
  fireEvent.click(screen.getByRole('button', { name: 'Web' })) // toggled back off
  fireEvent.click(screen.getByRole('button', { name: 'Tout Hacker News' }))
  fireEvent.click(screen.getByRole('button', { name: 'Élevée et plus' }))
  fireEvent.click(screen.getByRole('switch', { name: 'Inclure les infos non vérifiées et les rumeurs' }))
  fireEvent.change(screen.getByLabelText('Nombre maximum de news par édition'), { target: { value: '8' } })

  expect(screen.getByText('Modifications non enregistrées')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

  expect(await screen.findByText('Préférences enregistrées')).toBeInTheDocument()
  expect(api.calls.find((call) => call.method === 'PUT')?.body).toEqual({
    preferences: {
      language: 'fr',
      categories: ['cybersecurity'],
      sources: ['hackernews'],
      frequency: 'daily',
      min_importance: 'high',
      include_unconfirmed: false,
      max_items: 8,
    },
  })
})

test('rejects an out-of-range item limit before saving', async () => {
  const api = fakeApi([ada])
  renderAt(`/preferences/${ada.id}?lang=en`)
  await screen.findByRole('heading', { level: 2, name: 'ada@example.com' }, { timeout: 5000 })

  fireEvent.change(screen.getByLabelText('Maximum items per edition'), { target: { value: '500' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))

  expect(await screen.findByText('Between 1 and 100, or leave empty.')).toBeInTheDocument()
  expect(api.calls.some((call) => call.method === 'PUT')).toBe(false)
})

test('deletes a subscriber after confirmation', async () => {
  const api = fakeApi([ada])
  renderAt(`/preferences/${ada.id}?lang=en`)
  await screen.findByRole('heading', { level: 2, name: 'ada@example.com' }, { timeout: 5000 })

  fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
  const dialog = await screen.findByRole('alertdialog', { name: 'Delete this subscriber?' })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))

  await waitFor(() => expect(window.location.pathname).toBe('/preferences'))
  expect(api.subscribers).toEqual([])
  expect(await screen.findByText('No subscriber yet. Add the first one below.')).toBeInTheDocument()
})
