import { Trash2 } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

const DISSOLVE_MS = 900

type Props = { repoName: string; onBanish: () => Promise<void> }

export function BanishDialog({ repoName, onBanish }: Props) {
  const [open, setOpen] = useState(false)
  const [banishing, setBanishing] = useState(false)

  async function banish() {
    setBanishing(true)
    try {
      // Let the ghost finish dissolving even if the API answers faster.
      await Promise.all([onBanish(), new Promise((resolve) => setTimeout(resolve, DISSOLVE_MS))])
    } catch {
      setBanishing(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !banishing && setOpen(next)}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="w-full text-muted-foreground">
          <Trash2 /> Banish this ghost
        </Button>
      </DialogTrigger>
      <DialogContent className="border-destructive/30 text-center shadow-[0_0_80px_-20px] shadow-destructive/50 sm:max-w-md">
        <div className={cn('mx-auto my-2 text-6xl', banishing ? 'animate-banish' : 'animate-tremble')} aria-hidden>
          👻
        </div>
        <DialogHeader className="sm:text-center">
          <DialogTitle className="font-serif text-3xl font-semibold">Banish this ghost?</DialogTitle>
          <DialogDescription className="ghost-voice text-base">
            The ghost of <span className="text-foreground">{repoName}</span> will be laid to rest. Its memories,
            séance and parking notes fade forever.
          </DialogDescription>
        </DialogHeader>
        <p className="text-xs text-muted-foreground">Your GitHub repository is never touched.</p>
        <DialogFooter className="mt-2 gap-2 sm:justify-center">
          <Button variant="outline" onClick={() => setOpen(false)} disabled={banishing}>
            Let it linger
          </Button>
          <Button variant="destructive" onClick={banish} disabled={banishing}>
            {banishing ? 'Banishing...' : 'Banish'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
