import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { renderAt } from '../../test/render'
import settingsFixture from '../../test/fixtures/settings.json'

const KEY = 'AIza-test-value-never-shown'
type Call = { method: string; path: string; body: unknown }

function mockSettingsApi({
  settings = settingsFixture as unknown,
  secrets = [{ name: 'GOOGLE_API_KEY', used_by: ['ai:gemini'], in_file: false, in_environment: false }],
  put = (body: unknown): [number, unknown] => [200, { ...(settingsFixture as object), version: 'v2', values: (body as { values: unknown }).values }],
}: {
  settings?: unknown
  secrets?: unknown[]
  put?: (body: unknown) => [number, unknown]
} = {}) {
  const calls: Call[] = []
  let currentSecrets = secrets
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    const reply = (status: number, payload: unknown) => new Response(JSON.stringify(payload), { status })
    if (path === '/api/settings' && method === 'GET') return reply(200, settings)
    if (path === '/api/settings' && method === 'PUT') return reply(...put(body))
    if (path === '/api/settings/backups') return reply(200, { backups: [] })
    if (path === '/api/secrets') return reply(200, { secrets: currentSecrets })
    if (path.startsWith('/api/secrets/') && method === 'PUT') {
      currentSecrets = currentSecrets.map((secret) => ({ ...(secret as object), in_file: true }))
      return reply(200, { name: 'GOOGLE_API_KEY', in_file: true })
    }
    return reply(404, { error: 'not found' })
  })
  return calls
}

async function openSettings() {
  renderAt('/settings?lang=fr')
  return screen.findByRole('heading', { level: 1, name: 'Réglages' }, { timeout: 5000 })
}

test('shows the real settings and the key status', async () => {
  mockSettingsApi()
  await openSettings()

  expect(await screen.findByLabelText('Modèle')).toHaveValue('gemini-2.5-flash')
  expect(screen.getByLabelText('Variable de la clé')).toHaveValue('GOOGLE_API_KEY')
  expect(screen.getByRole('button', { name: /Français/ })).toHaveAttribute('aria-pressed', 'true')
  const keys = screen.getByRole('region', { name: 'Clés API' })
  expect(within(keys).getByText('GOOGLE_API_KEY')).toBeInTheDocument()
  expect(within(keys).getByText('Absente')).toBeInTheDocument()
  expect(within(keys).getByText('IA · gemini')).toBeInTheDocument()
})

test('saves edited settings with the version that was read', async () => {
  const calls = mockSettingsApi()
  await openSettings()

  const budget = await screen.findByLabelText('Budget de tokens par run')
  expect(budget).toHaveValue(200000) // from the example configuration
  fireEvent.change(budget, { target: { value: '150000' } })
  fireEvent.click(await screen.findByRole('button', { name: 'Enregistrer' }))

  expect(await screen.findByText('Enregistré. Appliqué dès le prochain run.')).toBeInTheDocument()
  const put = calls.find((call) => call.method === 'PUT' && call.path === '/api/settings')!
  expect(put.body).toMatchObject({
    version: (settingsFixture as { version: string }).version,
    values: { ai: { max_tokens_per_run: 150000, provider: 'gemini' } },
  })
})

test('a provider change proposes its usual model and key variable', async () => {
  mockSettingsApi()
  await openSettings()

  fireEvent.change(await screen.findByLabelText('Fournisseur'), { target: { value: 'anthropic' } })

  expect(screen.getByLabelText('Variable de la clé')).toHaveValue('ANTHROPIC_API_KEY')
  expect(screen.getByLabelText('Modèle')).not.toHaveValue('gemini-2.5-flash')
})

test('invalid values are stopped before sending, server refusals shown on the field', async () => {
  const calls = mockSettingsApi({
    put: () => [422, { error: 'invalid settings', fields: { 'ai.max_requests_per_minute': 'too high for this provider' } }],
  })
  await openSettings()

  fireEvent.click(await screen.findByRole('button', { name: /Français/ }))
  fireEvent.click(screen.getByRole('button', { name: /English/ }))
  fireEvent.click(await screen.findByRole('button', { name: 'Enregistrer' }))
  expect(await screen.findByText('Choisissez au moins une langue.')).toBeInTheDocument()
  expect(calls.some((call) => call.method === 'PUT')).toBe(false)

  fireEvent.click(screen.getByRole('button', { name: /Français/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
  expect(await screen.findByText('Le serveur a refusé cette valeur : too high for this provider')).toBeInTheDocument()
})

test('a configuration changed elsewhere asks to reload', async () => {
  mockSettingsApi({ put: () => [409, { error: 'the configuration changed since it was read' }] })
  await openSettings()

  fireEvent.change(await screen.findByLabelText('Fenêtre de collecte (heures)'), { target: { value: '48' } })
  fireEvent.click(await screen.findByRole('button', { name: 'Enregistrer' }))

  expect(await screen.findByText(/La configuration a changé ailleurs/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Recharger' })).toBeInTheDocument()
})

test('locked fields cannot be edited', async () => {
  mockSettingsApi({ settings: { ...(settingsFixture as object), locked: ['ai.model'] } })
  await openSettings()

  expect(await screen.findByLabelText('Modèle')).toBeDisabled()
  expect(screen.getByText('Défini par une variable dans config.json')).toBeInTheDocument()
})

test('a key is sent once and never shown again', async () => {
  const calls = mockSettingsApi()
  await openSettings()
  const keys = await screen.findByRole('region', { name: 'Clés API' })

  fireEvent.click(await within(keys).findByRole('button', { name: 'Saisir' }))
  const input = within(keys).getByLabelText('Valeur de GOOGLE_API_KEY')
  expect(input).toHaveAttribute('type', 'password')
  fireEvent.change(input, { target: { value: KEY } })
  fireEvent.click(within(keys).getByRole('button', { name: 'Enregistrer la clé' }))

  expect(await within(keys).findByText('Clé enregistrée. Elle ne sera plus affichée.')).toBeInTheDocument()
  expect(calls.find((call) => call.method === 'PUT' && call.path === '/api/secrets/GOOGLE_API_KEY')?.body).toEqual({ value: KEY })
  await waitFor(() => expect(within(keys).getByText('Enregistrée dans .env')).toBeInTheDocument())
  expect(within(keys).queryByLabelText('Valeur de GOOGLE_API_KEY')).toBeNull()
  expect(document.body.innerHTML).not.toContain(KEY)
})
