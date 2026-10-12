import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

const STORAGE_KEY = 'lucidnews.theme'
const THEME_COLOR = { light: '#F2F6F6', dark: '#0B0F1E' } as const

type ThemePreference = { dark: boolean; toggle: () => void }

const ThemeContext = createContext<ThemePreference | null>(null)

function storedDark(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'dark'
  } catch {
    return false
  }
}

/** Light by default; the reader's choice is kept in this browser (index.html applies it before first paint). */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(storedDark)

  useEffect(() => {
    const root = document.documentElement
    if (dark) root.dataset.theme = 'dark'
    else delete root.dataset.theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOR[dark ? 'dark' : 'light'])
  }, [dark])

  const value = useMemo<ThemePreference>(
    () => ({
      dark,
      toggle: () =>
        setDark((current) => {
          try {
            window.localStorage.setItem(STORAGE_KEY, current ? 'light' : 'dark')
          } catch {
            // Storage unavailable (private mode): the toggle still works for this visit.
          }
          return !current
        }),
    }),
    [dark],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemePreference {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used inside ThemeProvider')
  return context
}
