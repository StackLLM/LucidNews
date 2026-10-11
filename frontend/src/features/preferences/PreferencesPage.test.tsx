import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import options from '../../test/fixtures/preference-options.json'
import { renderAt } from '../../test/render'

// In-memory stand-in for the local subscriber routes (fictitious addresses only).
type Stored = {
  id: string
  email: string
  plan: 'free'
  preferences: Record<string, unknown>
  created_at: string
  status: 'pending' | 'confirmed' | 'unsubscribed'
  confirmed_at: string | null
  unsubscribed_at: string | null
}

const basePreferences = {
  language: 'en',
  categories: [],
  sources: [],
  frequency: 'daily',
  min_importance: null,
  include_unconfirmed: true,
  max_items: null,
  detail_level: 'complete',
}

const previewPayload = {
  frequency: 'daily',
  detail_level: 'complete',
  language: 'en',
  weekly_day: 0,
  reason: null,
  subject: 'LucidNews — 2026-10-11',
  html: '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><h1>Hello digest</h1></body></html>',
  text: 'Hello digest',
  item_count: 3,
  unanalyzed_count: 0,
  empty: false,
  would_send: true,
  edition: 'run-1',
}

function fakeApi(initial: Stored[] = [], preview: Record<string, unknown> = previewPayload, confirmation: Record<string, unknown> = { sent: true, error: null }, deliveries: unknown[] = []) {
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
        status: 'pending',
        confirmed_at: null,
        unsubscribed_at: null,
      }
      subscribers.push(created)
      return json({ ...created, confirmation: confirmation }, 201)
    }
    if (/^\/api\/subscribers\/\w+\/preview$/.test(path)) return json(preview)
    if (path === '/api/deliveries' || /^\/api\/subscribers\/\w+\/deliveries$/.test(path)) return json({ deliveries })
    const again = path.match(/^\/api\/subscribers\/(\w+)\/confirmation$/)
    if (again && method === 'POST') {
      const found = subscribers.find((s) => s.id === again[1])
      return found ? json({ ...found, confirmation }) : json({ error: 'not found' }, 404)
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
  status: 'confirmed',
  confirmed_at: '2026-10-02T09:00:00+00:00',
  unsubscribed_at: null,
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
      detail_level: 'complete',
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

test('the level of detail is saved with the preferences', async () => {
  const api = fakeApi([ada])
  renderAt(`/preferences/${ada.id}?lang=en`)
  await screen.findByRole('heading', { level: 2, name: 'ada@example.com' }, { timeout: 5000 })

  expect(screen.getByRole('button', { name: 'Complete' })).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(screen.getByRole('button', { name: 'Brief' }))
  expect(screen.getByText('Title, reliability, summary and source.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))

  expect(await screen.findByText('Preferences saved')).toBeInTheDocument()
  expect((api.calls.find((call) => call.method === 'PUT')?.body as { preferences: { detail_level: string } }).preferences.detail_level).toBe('brief')
})

test('the weekly choice says which day the digest is sent', async () => {
  fakeApi([{ ...ada, preferences: { ...basePreferences, frequency: 'weekly' } }])
  renderAt(`/preferences/${ada.id}?lang=en`)
  await screen.findByRole('heading', { level: 2, name: 'ada@example.com' }, { timeout: 5000 })

  expect(screen.getByText(/sent every Monday with the first run of that day/)).toBeInTheDocument()
})

test('the preview shows the e-mail in a frame without scripts', async () => {
  const api = fakeApi([ada])
  renderAt(`/preferences/${ada.id}?lang=en`)
  await screen.findByRole('heading', { level: 2, name: 'ada@example.com' }, { timeout: 5000 })

  // Nothing is built until it is asked for.
  expect(api.calls.some((call) => call.path.endsWith('/preview'))).toBe(false)
  fireEvent.click(screen.getByRole('button', { name: 'Show the preview' }))

  const frame = await screen.findByTitle('E-mail preview')
  expect(frame).toHaveAttribute('sandbox', 'allow-popups allow-popups-to-escape-sandbox')
  expect(frame.getAttribute('sandbox')).not.toContain('allow-scripts')
  expect(frame.getAttribute('srcdoc')).toContain('<h1>Hello digest</h1>')
  expect(screen.getByText('LucidNews — 2026-10-11')).toBeInTheDocument()
  expect(screen.getByText(/Latest published edition · 3 items/)).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Hide the preview' }))
  expect(screen.queryByTitle('E-mail preview')).not.toBeInTheDocument()
})

test('the preview says when there is nothing to show', async () => {
  fakeApi([ada], { ...previewPayload, reason: 'no_edition', subject: null, html: null, text: null, item_count: 0, empty: true, would_send: false })
  renderAt(`/preferences/${ada.id}?lang=en`)
  await screen.findByRole('heading', { level: 2, name: 'ada@example.com' }, { timeout: 5000 })

  fireEvent.click(screen.getByRole('button', { name: 'Show the preview' }))
  expect(await screen.findByText('No edition has been published yet. Run the pipeline once to get a preview.')).toBeInTheDocument()
})

test('a weekly preview with nothing to send is not shown as an e-mail', async () => {
  fakeApi([ada], { ...previewPayload, frequency: 'weekly', since: '2026-10-05', until: '2026-10-11', item_count: 0, empty: true, would_send: false })
  renderAt(`/preferences/${ada.id}?lang=en`)
  await screen.findByRole('heading', { level: 2, name: 'ada@example.com' }, { timeout: 5000 })

  fireEvent.click(screen.getByRole('button', { name: 'Show the preview' }))
  expect(await screen.findByText(/no weekly e-mail would be sent/)).toBeInTheDocument()
  expect(screen.queryByTitle('E-mail preview')).not.toBeInTheDocument()
})

// --- Double opt-in and delivery log (lot 22) ---------------------------------------------------------

const pendingReader: Stored = { ...ada, id: 'pen0000000000000', email: 'pending@example.com', status: 'pending', confirmed_at: null }

test('a new reader is pending and the page says what happened to the confirmation link', async () => {
  fakeApi([], previewPayload, { sent: false, error: 'Resend 422: invalid address' })
  renderAt('/preferences?lang=fr')
  await screen.findByText('Aucun abonné pour l’instant. Ajoutez le premier ci-dessous.', {}, { timeout: 5000 })

  fireEvent.change(screen.getByLabelText('Adresse e-mail'), { target: { value: 'new@example.com' } })
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }))

  const status = await screen.findByRole('region', { name: 'En attente de confirmation' })
  expect(within(status).getByText(/Rien ne lui est envoyé tant que son propriétaire/)).toBeInTheDocument()
  expect(within(status).getByText('Le lien de confirmation n’a pas pu être envoyé : Resend 422: invalid address')).toBeInTheDocument()
  expect(within(status).getByRole('button', { name: 'Renvoyer le lien' })).toBeInTheDocument()
})

test('the confirmation link can be sent again to a pending reader', async () => {
  const api = fakeApi([pendingReader])
  renderAt(`/preferences/${pendingReader.id}?lang=fr`)
  const status = await screen.findByRole('region', { name: 'En attente de confirmation' }, { timeout: 5000 })

  fireEvent.click(within(status).getByRole('button', { name: 'Envoyer le lien de confirmation' }))

  expect(await within(status).findByText('Lien de confirmation envoyé.')).toBeInTheDocument()
  expect(api.calls.some((call) => call.method === 'POST' && call.path.endsWith('/confirmation'))).toBe(true)
  // The list marks the reader who has not confirmed.
  expect(within(screen.getByRole('region', { name: /^Abonnés/ })).getByText('En attente de confirmation')).toBeInTheDocument()
})

test('a confirmed reader has no button, and says since when', async () => {
  fakeApi([ada])
  renderAt(`/preferences/${ada.id}?lang=fr`)
  const status = await screen.findByRole('region', { name: 'Confirmé' }, { timeout: 5000 })

  expect(within(status).getByText(/Confirmé le .*2 octobre 2026/)).toBeInTheDocument()
  expect(within(status).queryByRole('button')).not.toBeInTheDocument()
})

test('the delivery log lists each send with its result and error', async () => {
  fakeApi([ada], previewPayload, { sent: true, error: null }, [
    { id: 2, subscriber_id: ada.id, email: ada.email, kind: 'weekly', subject: 'LucidNews — semaine du 2026-10-05', reference: '2026-10-05', status: 'failed', error: 'Resend 422: invalid address', created_at: '2026-10-12T07:00:00+00:00' },
    { id: 1, subscriber_id: ada.id, email: ada.email, kind: 'daily', subject: 'LucidNews — 2026-10-11', reference: 'run-1', status: 'sent', error: null, created_at: '2026-10-11T07:00:00+00:00' },
  ])
  renderAt(`/preferences/${ada.id}?lang=fr`)
  const log = await screen.findByRole('region', { name: 'Journal des envois' }, { timeout: 5000 })

  expect(await within(log).findByText('Digest hebdomadaire')).toBeInTheDocument()
  expect(within(log).getByText('Resend 422: invalid address')).toBeInTheDocument()
  expect(within(log).getByText('Échec')).toBeInTheDocument()
  expect(within(log).getByText('Envoyé')).toBeInTheDocument()
  expect(within(log).getByText(/semaine du lundi 5 octobre 2026/)).toBeInTheDocument()
})

test('the overall log shows who each e-mail went to, and says when nothing was sent', async () => {
  fakeApi([ada])
  renderAt('/preferences?lang=fr')
  const log = await screen.findByRole('region', { name: 'Journal des envois' }, { timeout: 5000 })

  expect(await within(log).findByText('Rien n’a encore été envoyé.')).toBeInTheDocument()
})
