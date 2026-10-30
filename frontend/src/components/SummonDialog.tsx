import { Lock, Plus } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { api, daysSince, errorMessage, type GitHubRepo, type SyncResult, type TrackedRepo } from '@/lib/api'

export function SummonDialog() {
  const [open, setOpen] = useState(false)
  const [repos, setRepos] = useState<GitHubRepo[] | null>(null)
  const [query, setQuery] = useState('')
  const [summoning, setSummoning] = useState<string | null>(null)
  const navigate = useNavigate()

  function onOpenChange(next: boolean) {
    setOpen(next)
    if (next) {
      setRepos(null)
      api<GitHubRepo[]>('/api/github/repos')
        .then(setRepos)
        .catch((err) => toast.error(errorMessage(err)))
    }
  }

  async function summon(fullName: string) {
    setSummoning(fullName)
    try {
      const repo = await api<TrackedRepo>('/api/repos', { method: 'POST', body: { full_name: fullName } })
      // The ghost exists now; gathering its first memories can fail (e.g. Backboard down)
      // without losing the ghost, so the user can retry from the séance page.
      const toastId = toast.loading('The ghost is gathering its memories...')
      try {
        const sync = await api<SyncResult>(`/api/repos/${repo.id}/sync`, { method: 'POST' })
        toast.success(`Summoned. It remembers ${sync.new_commits} commits.`, { id: toastId })
      } catch (err) {
        toast.error(`Summoned, but its memories are faint: ${errorMessage(err)}`, { id: toastId })
      }
      setOpen(false)
      navigate(`/repos/${repo.id}`)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSummoning(null)
    }
  }

  const filtered = (repos ?? []).filter((r) => r.full_name.toLowerCase().includes(query.toLowerCase()))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus /> Summon a ghost
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Summon a ghost</DialogTitle>
          <DialogDescription>Pick a project you walked away from. Its ghost will learn from your commits.</DialogDescription>
        </DialogHeader>
        <Input placeholder="Search your repos..." value={query} onChange={(e) => setQuery(e.target.value)} autoFocus />
        <ul className="-mx-2 max-h-80 overflow-y-auto">
          {repos === null && <li className="px-2 py-6 text-center text-sm text-muted-foreground">Reading your repos...</li>}
          {filtered.map((r) => {
            const days = daysSince(r.pushed_at)
            return (
              <li key={r.full_name} className="flex items-center gap-3 rounded-md px-2 py-2 hover:bg-accent/40">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 truncate text-sm font-medium">
                    {r.full_name}
                    {r.private && <Lock className="size-3 text-muted-foreground" aria-label="private" />}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {/* GitHub's pushed_at also moves on branch/tag creation, not only new commits. */}
                    repo updated {days === 0 ? 'today' : `${days} days ago`}
                  </div>
                </div>
                {r.tracked ? (
                  <span className="text-xs text-muted-foreground">already haunted</span>
                ) : (
                  <Button size="sm" variant="outline" disabled={summoning !== null} onClick={() => summon(r.full_name)}>
                    {summoning === r.full_name ? 'Summoning...' : 'Summon'}
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      </DialogContent>
    </Dialog>
  )
}
