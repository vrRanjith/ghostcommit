import { Lock } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { Cobweb } from '@/components/Cobweb'
import { SummonDialog } from '@/components/SummonDialog'
import { UnlitCandle } from '@/components/UnlitCandle'
import { Badge } from '@/components/ui/badge'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api, daysSince, errorMessage, formatDate, type Me, type TrackedRepo } from '@/lib/api'

export function Dashboard({ me }: { me: Me }) {
  const [repos, setRepos] = useState<TrackedRepo[] | null>(null)

  useEffect(() => {
    api<TrackedRepo[]>('/api/repos')
      .then(setRepos)
      .catch((err) => toast.error(errorMessage(err)))
  }, [])

  return (
    <main>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-4xl font-semibold">Your haunted repos</h1>
          <p className="mt-1 text-muted-foreground">Projects you walked away from, and the ghosts that remember them.</p>
        </div>
        <SummonDialog />
      </div>

      {repos?.length === 0 && (
        <div className="rounded-xl border border-dashed py-16 text-center">
          <div className="animate-float text-5xl" aria-hidden>
            👻
          </div>
          <p className="ghost-voice mt-4 text-muted-foreground">No ghosts yet. Summon one from a project you abandoned.</p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {repos?.map((repo) => {
          const days = daysSince(repo.last_commit_at)
          const stalled = days !== null && days >= me.stall_days
          return (
            <Link key={repo.id} to={`/repos/${repo.id}`} className="group">
              <Card className="relative h-full overflow-hidden transition-colors group-hover:border-primary/50">
                {/* A year of silence grows cobwebs. */}
                {days !== null && days >= 365 && <Cobweb />}
                {/* No commits at all: a candle that was never lit. */}
                {repo.last_synced_at && !repo.last_commit_at && <UnlitCandle />}
                <CardHeader>
                  <CardTitle className="flex items-center gap-1.5 truncate">
                    {repo.full_name.split('/')[1]}
                    {repo.is_private && <Lock className="size-3.5 text-muted-foreground" aria-label="private" />}
                  </CardTitle>
                  <CardDescription className="truncate">{repo.full_name}</CardDescription>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                    {days === null ? (
                      <Badge variant="secondary">{repo.last_synced_at ? 'never awakened' : 'memories not gathered yet'}</Badge>
                    ) : stalled ? (
                      <span className="font-medium text-candle">Silent for {days} days</span>
                    ) : (
                      <span className="text-muted-foreground">Active {days === 0 ? 'today' : `${days} days ago`}</span>
                    )}
                    {repo.last_commit_at && (
                      <span className="text-xs text-muted-foreground">· last commit {formatDate(repo.last_commit_at)}</span>
                    )}
                  </div>
                  <p className="mt-4 text-sm text-primary opacity-70 transition-opacity group-hover:opacity-100">
                    Hold a séance →
                  </p>
                </CardHeader>
              </Card>
            </Link>
          )
        })}
      </div>
    </main>
  )
}
