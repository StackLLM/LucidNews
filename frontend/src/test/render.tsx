import { render } from '@testing-library/react'
import { vi } from 'vitest'
import { App, createQueryClient } from '../app/App'
import editionEn from './fixtures/edition-2026-10-06.en.json'
import editionFr from './fixtures/edition-2026-10-06.fr.json'
import editions from './fixtures/editions.json'
import sources from './fixtures/sources-30d.json'

// Fixtures are real API output from the local archive (6 Oct 2026 runs).
export const fixtures = { editionEn, editionFr, editions, sources }

type Routes = Partial<Record<'edition' | 'editions' | 'sources', unknown>>

/** Stub fetch with the API routes the screens call. `status` forces an error on every route. */
export function mockApi(overrides: Routes = {}, status = 200) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    let body: unknown = { error: 'not found' }
    if (url.pathname.startsWith('/api/editions/')) {
      body = overrides.edition ?? (url.searchParams.get('lang') === 'fr' ? editionFr : editionEn)
    } else if (url.pathname === '/api/editions') {
      body = overrides.editions ?? editions
    } else if (url.pathname === '/api/sources') {
      body = overrides.sources ?? sources
    }
    return new Response(JSON.stringify(status === 200 ? body : { error: 'down' }), { status })
  })
}

export function renderAt(path: string) {
  window.history.pushState({}, '', path)
  const queryClient = createQueryClient()
  queryClient.setDefaultOptions({ queries: { retry: false } })
  return render(<App queryClient={queryClient} />)
}
