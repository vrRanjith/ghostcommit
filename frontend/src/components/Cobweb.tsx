// A cobweb anchored in a card's top-right corner: radial threads plus sagging rings,
// generated once at module load (pure, no per-render work).
const CENTER = { x: 60, y: 0 }
const ANGLES = [180, 202, 225, 248, 270].map((deg) => (deg * Math.PI) / 180)
const RINGS = [13, 27, 43]

function point(r: number, a: number) {
  return { x: CENTER.x + r * Math.cos(a), y: CENTER.y - r * Math.sin(a) }
}

const threads = ANGLES.map((a) => {
  const end = point(60, a)
  return `M${CENTER.x} ${CENTER.y} L${end.x.toFixed(1)} ${end.y.toFixed(1)}`
})

// Each ring segment sags toward the corner like real silk.
const rings = RINGS.map((r) =>
  ANGLES.slice(1)
    .map((a, i) => {
      const from = point(r, ANGLES[i])
      const to = point(r, a)
      const sag = point(r * 0.82, (ANGLES[i] + a) / 2)
      return `${i === 0 ? `M${from.x.toFixed(1)} ${from.y.toFixed(1)} ` : ''}Q${sag.x.toFixed(1)} ${sag.y.toFixed(1)} ${to.x.toFixed(1)} ${to.y.toFixed(1)}`
    })
    .join(' '),
)

const WEB = [...threads, ...rings].join(' ')

export function Cobweb() {
  return (
    <svg
      viewBox="0 0 60 60"
      className="pointer-events-none absolute top-0 right-0 size-16 text-foreground/20"
      fill="none"
      stroke="currentColor"
      strokeWidth={0.6}
      aria-hidden
    >
      <path d={WEB} />
    </svg>
  )
}
