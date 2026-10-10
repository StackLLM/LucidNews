import { Activity, Archive, Gauge, Newspaper, Settings2, SlidersHorizontal, Zap, ZapOff, type LucideIcon } from 'lucide-react'
import { motion } from 'motion/react'
import { Link, NavLink, useLocation } from 'react-router'
import { languages, useLanguage, type MessageKey } from '../lib/i18n'
import { useMotionPreference } from '../lib/motion'

// shortKey: label of the phone and tablet bar, where six entries share the width.
const navItems: { key: MessageKey; shortKey?: MessageKey; icon: LucideIcon; to: string; matches: (path: string) => boolean }[] = [
  { key: 'nav.edition', icon: Newspaper, to: '/', matches: (path) => path === '/' || path.startsWith('/editions/') || path.startsWith('/items/') },
  { key: 'nav.archive', icon: Archive, to: '/archive', matches: (path) => path.startsWith('/archive') },
  { key: 'nav.sources', icon: Activity, to: '/sources', matches: (path) => path.startsWith('/sources') },
  { key: 'nav.preferences', shortKey: 'nav.short.preferences', icon: SlidersHorizontal, to: '/preferences', matches: (path) => path.startsWith('/preferences') },
  { key: 'nav.quality', icon: Gauge, to: '/quality', matches: (path) => path.startsWith('/quality') },
  { key: 'nav.settings', icon: Settings2, to: '/settings', matches: (path) => path.startsWith('/settings') },
]

export function TopBar() {
  const { language, setLanguage, t } = useLanguage()
  const motionPref = useMotionPreference()
  const { pathname } = useLocation()
  const search = `?lang=${language}`

  return (
    <>
      <header className="sticky top-3 z-30 mx-auto w-full max-w-6xl px-4 sm:top-5 sm:px-6">
        <div className="glass flex h-16 items-center gap-4 rounded-full pl-5 pr-2.5">
          <Link to={{ pathname: '/', search }} className="flex items-center gap-2.5">
            <LogoMark />
            <span className="text-[17px] font-bold tracking-tight">LucidNews</span>
          </Link>

          <nav className="ml-6 hidden items-center gap-1 lg:flex" aria-label={t('nav.main')}>
            {navItems.map(({ key, icon: Icon, to, matches }) => {
              const active = matches(pathname)
              return (
                <NavLink
                  key={key}
                  to={{ pathname: to, search }}
                  aria-current={active ? 'page' : undefined}
                  className={`relative flex items-center gap-2 rounded-full px-3.5 py-2 text-sm transition-colors duration-150 ${
                    active ? 'font-semibold text-accent' : 'font-medium text-muted hover:text-ink'
                  }`}
                >
                  <Icon size={16} aria-hidden />
                  {t(key)}
                  {active && (
                    <motion.span
                      layoutId="nav-underline"
                      transition={{ type: 'spring', stiffness: 380, damping: 34 }}
                      className="absolute inset-x-3.5 -bottom-[9px] h-0.5 rounded-full bg-accent"
                    />
                  )}
                </NavLink>
              )
            })}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <div role="group" aria-label={t('language.switch')} className="flex rounded-full bg-ink/[0.04] p-1">
              {languages.map((code) => (
                <button
                  key={code}
                  type="button"
                  aria-pressed={code === language}
                  onClick={() => setLanguage(code)}
                  className="relative rounded-full px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-muted transition-colors duration-150 hover:text-ink aria-pressed:text-ink"
                >
                  {code === language && (
                    <motion.span
                      layoutId="language-pill"
                      transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                      className="absolute inset-0 rounded-full bg-white shadow-sm"
                    />
                  )}
                  <span className="relative">{code}</span>
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={motionPref.toggle}
              aria-pressed={motionPref.enabled}
              aria-label={t(motionPref.enabled ? 'motion.on' : 'motion.off')}
              title={t(motionPref.enabled ? 'motion.on' : 'motion.off')}
              className="grid h-10 w-10 place-items-center rounded-full text-muted transition-all duration-150 ease-soft hover:bg-white hover:text-ink active:scale-95"
            >
              {motionPref.enabled ? <Zap size={17} aria-hidden /> : <ZapOff size={17} aria-hidden />}
            </button>
          </div>
        </div>
      </header>

      {/* Phone and tablet: the same destinations in a floating bar at the bottom. */}
      <nav
        aria-label={t('nav.main')}
        className="glass fixed inset-x-3 bottom-4 z-30 flex justify-around rounded-full px-1.5 py-1.5 lg:hidden"
        style={{ marginBottom: 'env(safe-area-inset-bottom)' }}
      >
        {navItems.map(({ key, shortKey, icon: Icon, to, matches }) => {
          const active = matches(pathname)
          return (
            <NavLink
              key={key}
              to={{ pathname: to, search }}
              aria-current={active ? 'page' : undefined}
              className={`flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-full px-0.5 py-1.5 text-[10.5px] font-semibold tracking-[-0.01em] transition-colors duration-150 ${
                active ? 'bg-accent-soft text-accent' : 'text-muted'
              }`}
            >
              <Icon size={18} aria-hidden />
              <span className="max-w-full truncate">{t(shortKey ?? key)}</span>
            </NavLink>
          )
        })}
      </nav>
    </>
  )
}

function LogoMark() {
  return (
    <span className="grid h-8 w-8 place-items-center rounded-[10px] bg-accent shadow-accent">
      <svg viewBox="0 0 20 20" className="h-4 w-4" aria-hidden>
        <circle cx="10" cy="10" r="6" fill="none" stroke="white" strokeWidth="2.2" />
        <circle cx="10" cy="10" r="2.2" fill="white" />
      </svg>
    </span>
  )
}
