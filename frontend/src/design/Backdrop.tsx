/** Page atmosphere: tinted canvas, faint rounded line pattern, two slow halos. */
export function Backdrop() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute -left-40 -top-48 h-[34rem] w-[34rem] animate-drift rounded-full bg-accent/12 blur-3xl" />
      <div className="absolute -right-32 top-1/3 h-[30rem] w-[30rem] animate-drift-slow rounded-full bg-teal-300/20 blur-3xl" />
      <svg className="absolute inset-0 h-full w-full text-ink/[0.05]" preserveAspectRatio="none">
        <defs>
          <pattern id="lucid-lines" width="360" height="300" patternUnits="userSpaceOnUse">
            <rect x="24" y="24" width="220" height="180" rx="48" fill="none" stroke="currentColor" />
            <rect x="200" y="150" width="200" height="190" rx="48" fill="none" stroke="currentColor" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#lucid-lines)" />
      </svg>
      <div className="absolute inset-x-0 bottom-0 h-64 bg-gradient-to-t from-canvas to-transparent" />
    </div>
  )
}
