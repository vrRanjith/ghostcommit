/** Marks a repo with no commits: a candle that was never lit, only a wisp of smoke. */
export function UnlitCandle() {
  return (
    <svg
      viewBox="0 0 40 60"
      className="pointer-events-none absolute top-4 right-5 h-14 w-10"
      fill="none"
      aria-hidden
    >
      {/* smoke curling up from the dead wick */}
      <path
        className="candle-smoke"
        d="M20 22 C16 17 24 13 20 8 C17 4 22 1 20 -3"
        stroke="var(--muted-foreground)"
        strokeWidth={1.2}
        strokeLinecap="round"
      />
      {/* curled, burnt-out wick */}
      <path d="M20 31 C20 28 21 27 19.5 25" stroke="oklch(0.35 0.02 290)" strokeWidth={1.4} strokeLinecap="round" />
      {/* wax body with a drip over the rim */}
      <rect x={13} y={30} width={14} height={24} rx={2} fill="oklch(0.86 0.03 85 / 22%)" />
      <path d="M13 32 Q13 30 15 30 H25 Q27 30 27 32 V36 Q25.5 37 25.5 39 Q25.5 41 24 41 Q22.5 41 22.5 38 V34 H13 Z" fill="oklch(0.86 0.03 85 / 32%)" />
      {/* holder */}
      <ellipse cx={20} cy={55} rx={11} ry={3} fill="oklch(0.5 0.03 290 / 40%)" />
    </svg>
  )
}
