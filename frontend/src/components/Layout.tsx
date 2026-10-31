import { LogOut } from 'lucide-react'
import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { toast } from 'sonner'

import { SettingsDialog } from '@/components/SettingsDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api, HAUNTINGS_CHANGED_EVENT, RECONNECT_EVENT, type Haunting, type Me } from '@/lib/api'
import { cn } from '@/lib/utils'

type Props = { me: Me; onMeChange: (me: Me) => void; onLogout: () => void }

const POLL_MS = 60_000

// Where each ghost starts, which way it drifts, and when: staggered so they never sync up.
// CSSProperties doesn't know custom properties, so also allow any `--name` key.
const HOVERING_GHOSTS: (CSSProperties & Record<`--${string}`, string>)[] = [
  { top: -14, left: -10, '--dx': '-6px', '--dy': '-8px', animationDelay: '0s' },
  { top: -16, right: -8, '--dx': '7px', '--dy': '-6px', animationDelay: '1.5s' },
  { bottom: -14, right: 14, '--dx': '5px', '--dy': '7px', animationDelay: '3s' },
]

export function Layout({ me, onMeChange, onLogout }: Props) {
  const [unread, setUnread] = useState(0)
  const [reconnect, setReconnect] = useState(false)
  const lastUnread = useRef<number | null>(null)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    const refresh = () =>
      api<Haunting[]>('/api/hauntings')
        .then((hs) => {
          const count = hs.filter((h) => !h.read).length
          // Announce hauntings that arrived while the page was open (not the ones present on load).
          if (lastUnread.current !== null && count > lastUnread.current) {
            toast('👻 A ghost has come for you', {
              description: 'One of your abandoned projects is calling.',
              action: { label: 'View', onClick: () => navigate('/hauntings') },
            })
          }
          lastUnread.current = count
          setUnread(count)
        })
        .catch(() => {})
    // Hauntings are written by the daily job, not by this page, so look again periodically and
    // when the user comes back to the tab. Hidden tabs don't poll.
    const refreshIfVisible = () => document.visibilityState === 'visible' && refresh()
    refresh()
    const timer = setInterval(refreshIfVisible, POLL_MS)
    document.addEventListener('visibilitychange', refreshIfVisible)
    window.addEventListener(HAUNTINGS_CHANGED_EVENT, refresh)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', refreshIfVisible)
      window.removeEventListener(HAUNTINGS_CHANGED_EVENT, refresh)
    }
  }, [location.pathname, navigate])

  useEffect(() => {
    const show = () => setReconnect(true)
    window.addEventListener(RECONNECT_EVENT, show)
    return () => window.removeEventListener(RECONNECT_EVENT, show)
  }, [])

  async function logout() {
    await api('/auth/logout', { method: 'POST' })
    onLogout()
  }

  const navClass = ({ isActive }: { isActive: boolean }) =>
    cn('rounded-md px-3 py-1.5 text-sm transition-colors', isActive ? 'bg-accent text-foreground' : 'text-muted-foreground hover:text-foreground')

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
      <header className="flex items-center gap-2 py-5">
        <NavLink to="/" className="mr-4 flex items-center gap-2 font-serif text-xl font-semibold">
          <span aria-hidden>👻</span> GhostCommit
        </NavLink>
        <nav className="flex items-center gap-1">
          <NavLink to="/" end className={navClass}>
            Haunted repos
          </NavLink>
          <span className="relative">
            <NavLink to="/hauntings" className={navClass}>
              Hauntings
              {unread > 0 && <Badge className="ml-2 h-5 px-1.5">{unread}</Badge>}
            </NavLink>
            {unread > 0 &&
              HOVERING_GHOSTS.map((g, i) => (
                <span key={i} className="haunting-ghost" style={g} aria-hidden>
                  👻
                </span>
              ))}
          </span>
        </nav>
        <div className="ml-auto flex items-center gap-1">
          <SettingsDialog me={me} onSaved={onMeChange} />
          {me.avatar_url && <img src={me.avatar_url} alt={me.login} className="ml-1 size-8 rounded-full border" />}
          <Button variant="ghost" size="icon" onClick={logout} aria-label="Log out">
            <LogOut />
          </Button>
        </div>
      </header>

      {reconnect && (
        <div className="mb-6 flex items-center justify-between rounded-lg border border-candle/40 bg-candle/10 px-4 py-3 text-sm">
          <span>The ghost lost its link to GitHub. Your connection expired or was revoked.</span>
          <Button asChild size="sm">
            <a href="/auth/github/login">Reconnect GitHub</a>
          </Button>
        </div>
      )}

      <Outlet />
    </div>
  )
}
