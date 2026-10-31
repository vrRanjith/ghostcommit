import { Mail, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { WindGust } from '@/components/WindGust'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { api, errorMessage, formatDate, HAUNTINGS_CHANGED_EVENT, type Haunting } from '@/lib/api'
import { cn } from '@/lib/utils'

const FADE_MS = 450

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export function Hauntings() {
  const [hauntings, setHauntings] = useState<Haunting[] | null>(null)
  const [leaving, setLeaving] = useState<Set<number>>(new Set())
  const [confirmOpen, setConfirmOpen] = useState(false)

  useEffect(() => {
    // Ignore results from a superseded run (StrictMode runs effects twice in dev); otherwise
    // run #1 marks everything read and run #2 renders it without the unread glow.
    let cancelled = false
    api<Haunting[]>('/api/hauntings')
      .then(async (hs) => {
        if (cancelled) return
        setHauntings(hs)
        // Opening the feed counts as reading it; keep the highlight for this visit.
        const unread = hs.filter((h) => !h.read)
        await Promise.all(unread.map((h) => api(`/api/hauntings/${h.id}/read`, { method: 'POST' })))
        if (unread.length) window.dispatchEvent(new Event(HAUNTINGS_CHANGED_EVENT))
      })
      .catch((err) => toast.error(errorMessage(err)))
    return () => {
      cancelled = true
    }
  }, [])

  // Fade the cards out while the delete runs, then drop them from the list.
  async function layToRest(ids: number[], request: Promise<unknown>) {
    setLeaving((prev) => new Set([...prev, ...ids]))
    try {
      await Promise.all([request, wait(FADE_MS)])
      setHauntings((prev) => prev?.filter((h) => !ids.includes(h.id)) ?? prev)
      window.dispatchEvent(new Event(HAUNTINGS_CHANGED_EVENT))
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setLeaving((prev) => new Set([...prev].filter((id) => !ids.includes(id))))
    }
  }

  function dismiss(id: number) {
    layToRest([id], api(`/api/hauntings/${id}`, { method: 'DELETE' }))
  }

  async function dismissAll() {
    setConfirmOpen(false)
    await layToRest(hauntings?.map((h) => h.id) ?? [], api('/api/hauntings', { method: 'DELETE' }))
    toast.success('All hauntings have been laid to rest.')
  }

  return (
    <main className="mx-auto max-w-3xl">
      <WindGust />
      <div className="mt-1 mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-4xl font-semibold">Hauntings</h1>
          <p className="mt-1 text-muted-foreground">When a project goes quiet for too long, its ghost comes looking for you.</p>
        </div>
        {!!hauntings?.length && (
          <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                Lay all to rest
              </Button>
            </DialogTrigger>
            <DialogContent className="text-center sm:max-w-md">
              <DialogHeader className="sm:text-center">
                <DialogTitle className="font-serif text-2xl">Lay all hauntings to rest?</DialogTitle>
                <DialogDescription className="ghost-voice text-base">
                  Every message in this feed fades away. Your ghosts, their memories and your notes remain, and they
                  will still come for you if you stay away too long.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter className="gap-2 sm:justify-center">
                <Button variant="outline" onClick={() => setConfirmOpen(false)}>
                  Keep them
                </Button>
                <Button onClick={dismissAll}>Lay to rest</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {hauntings?.length === 0 && (
        <div className="rounded-xl border border-dashed py-16 text-center">
          <p className="ghost-voice text-muted-foreground">All is quiet. No ghost has come for you yet.</p>
        </div>
      )}

      <div className="space-y-4">
        {hauntings?.map((h, i) => {
          const isLeaving = leaving.has(h.id)
          return (
            <Card
              key={h.id}
              // Carried in by the gust one after another; fades away when laid to rest.
              style={isLeaving ? undefined : { animationDelay: `${0.3 + i * 0.15}s` }}
              className={cn(
                isLeaving ? 'animate-fade-away' : 'animate-blown-in',
                !h.read && 'border-primary/50 shadow-[0_0_30px_-12px] shadow-primary/40',
              )}
            >
              <CardContent>
                <div className="mb-3 flex items-center gap-2 text-sm">
                  <Link to={`/repos/${h.repo_id}`} className="font-medium hover:text-primary">
                    👻 {h.repo}
                  </Link>
                  <span className="text-muted-foreground">· {formatDate(h.created_at)}</span>
                  <div className="ml-auto flex items-center gap-1">
                    {h.emailed && <Mail className="size-4 text-muted-foreground" aria-label="also sent by email" />}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => dismiss(h.id)}
                      disabled={isLeaving}
                      aria-label="Lay this haunting to rest"
                      title="Lay to rest"
                      className="text-muted-foreground"
                    >
                      <X />
                    </Button>
                  </div>
                </div>
                <p className="ghost-voice whitespace-pre-wrap">{h.message}</p>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </main>
  )
}
