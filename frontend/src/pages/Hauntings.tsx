import { Mail } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { WindGust } from '@/components/WindGust'
import { Card, CardContent } from '@/components/ui/card'
import { api, errorMessage, formatDate, HAUNTINGS_CHANGED_EVENT, type Haunting } from '@/lib/api'
import { cn } from '@/lib/utils'

export function Hauntings() {
  const [hauntings, setHauntings] = useState<Haunting[] | null>(null)

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

  return (
    <main className="mx-auto max-w-3xl">
      <WindGust />
      <h1 className="font-serif text-4xl font-semibold">Hauntings</h1>
      <p className="mt-1 mb-8 text-muted-foreground">
        When a project goes quiet for too long, its ghost comes looking for you.
      </p>

      {hauntings?.length === 0 && (
        <div className="rounded-xl border border-dashed py-16 text-center">
          <p className="ghost-voice text-muted-foreground">All is quiet. No ghost has come for you yet.</p>
        </div>
      )}

      <div className="space-y-4">
        {hauntings?.map((h, i) => (
          <Card
            key={h.id}
            // Carried in by the gust, one after another.
            style={{ animationDelay: `${0.3 + i * 0.15}s` }}
            className={cn(
              'animate-blown-in',
              !h.read && 'border-primary/50 shadow-[0_0_30px_-12px] shadow-primary/40',
            )}
          >
            <CardContent>
              <div className="mb-3 flex items-center gap-2 text-sm">
                <Link to={`/repos/${h.repo_id}`} className="font-medium hover:text-primary">
                  👻 {h.repo}
                </Link>
                <span className="text-muted-foreground">· {formatDate(h.created_at)}</span>
                {h.emailed && <Mail className="ml-auto size-4 text-muted-foreground" aria-label="also sent by email" />}
              </div>
              <p className="ghost-voice whitespace-pre-wrap">{h.message}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  )
}
