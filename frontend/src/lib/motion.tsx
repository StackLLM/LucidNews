import { LazyMotion, MotionConfig, type Transition, type Variants } from 'motion/react'
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

const STORAGE_KEY = 'lucidnews.motion'

// The animation engine (layout animations included) is fetched after the first paint, not shipped in the core bundle.
const loadFeatures = () => import('./motionFeatures').then((module) => module.default)

export const easeSoft = [0.22, 1, 0.36, 1] as const

export const listStagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } },
}

export const riseIn: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: easeSoft } },
}

export const expand: Transition = { duration: 0.25, ease: easeSoft }

type MotionPreference = { enabled: boolean; toggle: () => void }

const MotionContext = createContext<MotionPreference | null>(null)

function systemPrefersReduced(): boolean {
  return typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

function storedPreference(): boolean | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    return value === null ? null : value === 'on'
  } catch {
    return null
  }
}

/** Animations on/off: the user's choice wins, otherwise the OS setting. */
export function MotionProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabled] = useState(() => storedPreference() ?? !systemPrefersReduced())

  useEffect(() => {
    document.documentElement.dataset.motion = enabled ? 'on' : 'off'
  }, [enabled])

  const value = useMemo<MotionPreference>(
    () => ({
      enabled,
      toggle: () =>
        setEnabled((current) => {
          try {
            window.localStorage.setItem(STORAGE_KEY, current ? 'off' : 'on')
          } catch {
            // Storage unavailable (private mode): the toggle still works for this visit.
          }
          return !current
        }),
    }),
    [enabled],
  )

  return (
    <MotionContext.Provider value={value}>
      <LazyMotion features={loadFeatures} strict>
        <MotionConfig reducedMotion={enabled ? 'never' : 'always'}>{children}</MotionConfig>
      </LazyMotion>
    </MotionContext.Provider>
  )
}

export function useMotionPreference(): MotionPreference {
  const context = useContext(MotionContext)
  if (!context) throw new Error('useMotionPreference must be used inside MotionProvider')
  return context
}
