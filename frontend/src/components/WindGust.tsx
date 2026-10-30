import { useEffect, useState, type CSSProperties } from 'react'

type Vars = CSSProperties & Record<`--${string}`, string>

// Wind wisps in a 1600x900 box: wavy, and some curl at the end the way gusts are drawn.
// Each is drawn as a short dash that travels along the curve (see .wind-line in index.css).
const WISPS: { d: string; style: Vars; width: number }[] = [
  {
    d: 'M -100 260 C 150 200 350 320 600 250 S 1000 180 1200 260 C 1300 300 1320 380 1250 390 C 1190 398 1180 330 1230 320',
    style: { '--dur': '2.2s', '--delay': '0s', '--o': '0.8' },
    width: 2.5,
  },
  {
    d: 'M -150 520 C 200 470 420 600 760 520 S 1180 440 1500 530',
    style: { '--dur': '2s', '--delay': '0.2s', '--o': '0.55' },
    width: 4,
  },
  {
    d: 'M -80 700 C 250 650 500 760 820 690 C 1000 650 1080 600 1150 640 C 1220 680 1200 750 1140 745 C 1090 740 1095 690 1140 690',
    style: { '--dur': '2.4s', '--delay': '0.35s', '--o': '0.75' },
    width: 2,
  },
  {
    d: 'M -120 380 C 300 360 520 430 900 380 S 1400 330 1700 400',
    style: { '--dur': '1.8s', '--delay': '0.1s', '--o': '0.4' },
    width: 6,
  },
  {
    d: 'M -60 140 C 220 110 480 190 760 140 C 950 105 1050 160 1080 200 C 1105 240 1060 270 1030 245 C 1005 222 1030 195 1060 205',
    style: { '--dur': '2.1s', '--delay': '0.5s', '--o': '0.65' },
    width: 2,
  },
  {
    d: 'M -100 820 C 300 790 600 850 1000 800 S 1450 760 1700 820',
    style: { '--dur': '2s', '--delay': '0.25s', '--o': '0.45' },
    width: 3,
  },
]

// Ghosts caught in the gust. Height (--y), bob amplitude/speed and tumble speed differ per
// ghost; bigger = nearer = slightly faster, which gives a sense of depth.
const GHOSTS: Vars[] = [
  { fontSize: 38, '--y': '26vh', '--amp': '6vh', '--bob': '0.7s', '--tumble': '0.9s', '--dur': '2.6s', '--delay': '0.2s', '--o': '0.95' },
  { fontSize: 24, '--y': '64vh', '--amp': '4vh', '--bob': '0.55s', '--tumble': '0.7s', '--dur': '3.1s', '--delay': '0.45s', '--o': '0.75' },
  { fontSize: 31, '--y': '10vh', '--amp': '5vh', '--bob': '0.8s', '--tumble': '1.1s', '--dur': '2.9s', '--delay': '0.7s', '--o': '0.85' },
]

const GUST_MS = 4000

/** One gust of spectral wind that carries a few ghosts across the screen, then removes itself. */
export function WindGust() {
  const [blowing, setBlowing] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => setBlowing(false), GUST_MS)
    return () => clearTimeout(timer)
  }, [])

  if (!blowing) return null
  return (
    <div className="pointer-events-none fixed inset-0 z-40 overflow-hidden" aria-hidden>
      <div className="wind-mist" />
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1600 900" preserveAspectRatio="none">
        {WISPS.map((w, i) => (
          <path key={i} d={w.d} pathLength={1000} className="wind-line" strokeWidth={w.width} style={w.style} />
        ))}
      </svg>
      {GHOSTS.map((style, i) => (
        // drift (across) > bob (up/down) > tumble (rotate): three simple motions, one smooth flight.
        <span key={i} className="wind-ghost" style={style}>
          <span className="wind-ghost-bob">
            <span className="wind-ghost-tumble">👻</span>
          </span>
        </span>
      ))}
    </div>
  )
}
