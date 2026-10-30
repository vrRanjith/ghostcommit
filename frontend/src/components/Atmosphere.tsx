import type { CSSProperties } from 'react'

type Vars = CSSProperties & Record<`--${string}`, string>

// Spirit motes rising through the room. Hand-placed (not random) so renders stay pure.
const MOTES: Vars[] = [
  { '--x': '6%', '--s': '3px', '--dur': '18s', '--delay': '0s', '--sway': '30px', '--o': '0.7' },
  { '--x': '14%', '--s': '2px', '--dur': '24s', '--delay': '6s', '--sway': '-20px', '--o': '0.5' },
  { '--x': '23%', '--s': '4px', '--dur': '21s', '--delay': '11s', '--sway': '25px', '--o': '0.45' },
  { '--x': '31%', '--s': '2px', '--dur': '16s', '--delay': '3s', '--sway': '-35px', '--o': '0.65' },
  { '--x': '42%', '--s': '3px', '--dur': '26s', '--delay': '14s', '--sway': '20px', '--o': '0.5' },
  { '--x': '51%', '--s': '2px', '--dur': '19s', '--delay': '8s', '--sway': '-25px', '--o': '0.7' },
  { '--x': '60%', '--s': '3px', '--dur': '23s', '--delay': '1s', '--sway': '35px', '--o': '0.55' },
  { '--x': '68%', '--s': '2px', '--dur': '17s', '--delay': '12s', '--sway': '-15px', '--o': '0.65' },
  { '--x': '77%', '--s': '4px', '--dur': '25s', '--delay': '5s', '--sway': '25px', '--o': '0.4' },
  { '--x': '85%', '--s': '2px', '--dur': '20s', '--delay': '9s', '--sway': '-30px', '--o': '0.6' },
  { '--x': '93%', '--s': '3px', '--dur': '22s', '--delay': '15s', '--sway': '20px', '--o': '0.5' },
  { '--x': '48%', '--s': '2px', '--dur': '28s', '--delay': '19s', '--sway': '-40px', '--o': '0.45' },
]

/** Ambient background for every page: candle glow, fog, rising motes, a distant ghost, vignette. */
export function Atmosphere() {
  return (
    <div className="atmosphere" aria-hidden>
      <div className="candle-glow" />
      <div className="fog" />
      <div className="fog fog-2" />
      {MOTES.map((style, i) => (
        <span key={i} className="mote" style={style} />
      ))}
      <span className="wanderer">
        <span className="wanderer-bob">👻</span>
      </span>
      <div className="vignette" />
    </div>
  )
}
