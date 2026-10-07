import { useEffect, useState } from 'react'
import { useMotionPreference } from '../lib/motion'

/** Counts from 0 to `value` once, on mount. Shows the final value when animations are off. */
export function CountUp({ value, duration = 900 }: { value: number; duration?: number }) {
  const { enabled } = useMotionPreference()
  const [shown, setShown] = useState(enabled ? 0 : value)

  useEffect(() => {
    // Hidden tabs pause animation frames: show the real figure instead of a frozen 0.
    if (!enabled || document.hidden) {
      setShown(value)
      return
    }
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, Math.max(0, (now - start) / duration))
      setShown(Math.round(value * (1 - (1 - progress) ** 3)))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value, duration, enabled])

  return <span className="tabular-nums">{shown}</span>
}
