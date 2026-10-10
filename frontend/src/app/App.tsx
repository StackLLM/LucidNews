import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { Backdrop } from '../design/Backdrop'
import { PageSkeleton } from '../design/PageState'
import { useLanguage } from '../lib/i18n'
import { MotionProvider } from '../lib/motion'
import { TopBar } from './TopBar'

// One chunk per screen: charts and the calendar load only where they are used.
const EditionPage = lazy(() => import('../features/edition/EditionPage').then((m) => ({ default: m.EditionPage })))
const ArchivePage = lazy(() => import('../features/archive/ArchivePage').then((m) => ({ default: m.ArchivePage })))
const ItemPage = lazy(() => import('../features/item/ItemPage').then((m) => ({ default: m.ItemPage })))
const PreferencesPage = lazy(() =>
  import('../features/preferences/PreferencesPage').then((m) => ({ default: m.PreferencesPage })),
)
const QualityPage = lazy(() => import('../features/quality/QualityPage').then((m) => ({ default: m.QualityPage })))
const SettingsPage = lazy(() => import('../features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const SourcesPage = lazy(() => import('../features/sources/SourcesPage').then((m) => ({ default: m.SourcesPage })))

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { staleTime: 60_000, retry: 1, refetchOnWindowFocus: false } },
  })
}

export function Shell() {
  const { language } = useLanguage()
  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  return (
    <>
      <Backdrop />
      <TopBar />
      <main className="mx-auto w-full max-w-6xl px-4 pb-32 pt-8 sm:px-6 sm:pt-10 lg:pb-24">
        <Suspense fallback={<PageSkeleton />}>
          <Routes>
            <Route path="/" element={<EditionPage />} />
            <Route path="/editions/:editionId" element={<EditionPage />} />
            <Route path="/items/:itemId" element={<ItemPage />} />
            <Route path="/archive" element={<ArchivePage />} />
            <Route path="/sources" element={<SourcesPage />} />
            <Route path="/preferences" element={<PreferencesPage />} />
            <Route path="/quality" element={<QualityPage />} />
            <Route path="/quality/results" element={<QualityPage />} />
            <Route path="/preferences/:subscriberId" element={<PreferencesPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
    </>
  )
}

export function App({ queryClient = createQueryClient() }: { queryClient?: QueryClient }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MotionProvider>
        <BrowserRouter>
          <Shell />
        </BrowserRouter>
      </MotionProvider>
    </QueryClientProvider>
  )
}
