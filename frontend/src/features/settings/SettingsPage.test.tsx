import { fireEvent, screen } from '@testing-library/react'
import { vi } from 'vitest'
import { renderAt } from '../../test/render'
import settingsFixture from '../../test/fixtures/settings.json'

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
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    const reply = (status: number, payload: unknown) => new Response(JSON.stringify(payload), { status })
    if (path === '/api/settings' && method === 'GET') return reply(200, settings)
    if (path === '/api/settings' && method === 'PUT') return reply(...put(body))
    if (path === '/api/settings/backups') return reply(200, { backups: [] })
    if (path === '/api/secrets') return reply(200, { secrets })
    return reply(404, { error: 'not found' })
  })
  return calls
}

async function openSettings() {
  renderAt('/settings?lang=fr')
  return screen.findByRole('heading', { level: 1, name: 'Réglages' }, { timeout: 5000 })
}

const withAi = (enabled: boolean) => ({
  ...(settingsFixture as { values: { ai: object } }),
  values: { ...(settingsFixture as { values: object }).values, ai: { ...(settingsFixture as { values: { ai: object } }).values.ai, enabled } },
})

test('shows the real settings and the key status', async () => {
  mockSettingsApi()
  await openSettings()

  expect(await screen.findByLabelText('Modèle')).toHaveValue('gemini-2.5-flash')
  expect(screen.getByLabelText('Variable de la clé')).toHaveValue('GOOGLE_API_KEY')
  expect(screen.getByRole('button', { name: /Français/ })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText(/Clé GOOGLE_API_KEY · non détectée/)).toBeInTheDocument()
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

test('AI analysis is an opt-in checkbox: off hides the provider settings and needs no key', async () => {
  mockSettingsApi({ settings: withAi(false) })
  await openSettings()

  const box = await screen.findByRole('checkbox', { name: 'Activer l’analyse par IA' })
  expect(box).not.toBeChecked()
  expect(screen.queryByLabelText('Fournisseur')).toBeNull()
  expect(screen.queryByText(/non détectée/)).toBeNull()
  // Languages stay editable: they also name the digest languages.
  expect(screen.getByRole('button', { name: /Français/ })).toBeInTheDocument()
})

test('ticking the box saves ai.enabled and reveals the provider settings', async () => {
  const calls = mockSettingsApi({ settings: withAi(false) })
  await openSettings()

  fireEvent.click(await screen.findByRole('checkbox', { name: 'Activer l’analyse par IA' }))
  expect(await screen.findByLabelText('Fournisseur')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

  await screen.findByText('Enregistré. Appliqué dès le prochain run.')
  const put = calls.find((call) => call.method === 'PUT' && call.path === '/api/settings')!
  expect(put.body).toMatchObject({ values: { ai: { enabled: true } } })
})

test('no key can be typed in the interface, and none is ever sent', async () => {
  const calls = mockSettingsApi({ secrets: [{ name: 'GOOGLE_API_KEY', used_by: ['ai:gemini'], in_file: true, in_environment: false }] })
  await openSettings()

  expect(await screen.findByText(/Clé GOOGLE_API_KEY · détectée/)).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Clés API' })).toBeNull()
  expect(document.querySelector('input[type="password"]')).toBeNull()
  expect(screen.queryByRole('button', { name: /Saisir|Enregistrer la clé/ })).toBeNull()
  expect(screen.getByText(/ne se saisissent jamais ici/)).toBeInTheDocument()
  expect(calls.some((call) => call.path.startsWith('/api/secrets') && call.method !== 'GET')).toBe(false)
})
