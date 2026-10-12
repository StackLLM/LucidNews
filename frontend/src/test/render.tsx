import { render } from '@testing-library/react'
import { vi } from 'vitest'
import { App, createQueryClient } from '../app/App'
import editionEn from './fixtures/edition-2026-10-06.en.json'
import editionFr from './fixtures/edition-2026-10-06.fr.json'
import editions from './fixtures/editions.json'
import itemEn from './fixtures/item-curl.en.json'
import itemFr from './fixtures/item-curl.fr.json'
import sources from './fixtures/sources-30d.json'

// Fixtures are real API output from the local archive (6 Oct 2026 runs).
export const fixtures = { editionEn, editionFr, editions, itemEn, itemFr, sources }

type Routes = Partial<Record<'edition' | 'editions' | 'item' | 'sources', unknown>>

/** The API without accounts (auth.enabled off): the app stays open, as it always was. */
export const noAccounts = { enabled: false, authenticated: false, user: null, signup_enabled: false, providers: { google: false } }

/** Stub fetch with the API routes the screens call. `status` forces an error on every route. */
export function mockApi(overrides: Routes = {}, status = 200) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    let body: unknown = { error: 'not found' }
    if (url.pathname.startsWith('/api/items/')) {
      body = overrides.item ?? (url.searchParams.get('lang') === 'fr' ? itemFr : itemEn)
    } else if (url.pathname.startsWith('/api/editions/')) {
      body = overrides.edition ?? (url.searchParams.get('lang') === 'fr' ? editionFr : editionEn)
    } else if (url.pathname === '/api/editions') {
      body = overrides.editions ?? editions
    } else if (url.pathname === '/api/sources') {
      body = overrides.sources ?? sources
    } else if (url.pathname.startsWith('/api/sources/config')) {
      // Like an API not bound to localhost: the Sources page stays read only.
      return new Response(JSON.stringify({ error: 'only available when the API is bound to localhost' }), { status: 403 })
    }
    return new Response(JSON.stringify(status === 200 ? body : { error: 'down' }), { status })
  })
}

/**
 * Every screen asks who the reader is first. Unless a test says otherwise the answer is "accounts
 * are off", whatever API double the test installed for its own routes.
 */
export function answerSession(session: unknown = noAccounts) {
  const inner = globalThis.fetch
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) =>
    new URL(String(input), 'http://localhost').pathname === '/api/auth/session' ? new Response(JSON.stringify(session), { status: 200 }) : inner(input, init),
  )
}

export function renderAt(path: string, session: unknown = noAccounts) {
  answerSession(session)
  window.history.pushState({}, '', path)
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false } })
  return render(<App queryClient={queryClient} />)
}
