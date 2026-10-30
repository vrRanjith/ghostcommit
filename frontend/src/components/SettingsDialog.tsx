import { Settings } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { api, errorMessage, type Me } from '@/lib/api'

export function SettingsDialog({ me, onSaved }: { me: Me; onSaved: (me: Me) => void }) {
  const [open, setOpen] = useState(false)
  const [notifyEmail, setNotifyEmail] = useState(me.notify_email)
  const [stallDays, setStallDays] = useState(me.stall_days)
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      onSaved(await api<Me>('/api/me', { method: 'PATCH', body: { notify_email: notifyEmail, stall_days: stallDays } }))
      toast.success('Settings saved')
      setOpen(false)
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Settings">
          <Settings />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Haunting settings</DialogTitle>
          <DialogDescription>Decide when and how your ghosts reach out.</DialogDescription>
        </DialogHeader>
        <div className="space-y-5 py-2">
          <div className="flex items-center justify-between gap-4">
            <Label htmlFor="notify-email" className="flex-col items-start gap-1">
              <span>Email hauntings</span>
              <span className="text-xs font-normal text-muted-foreground">
                {me.email ? `Sent to ${me.email}` : 'No verified email on your GitHub account'}
              </span>
            </Label>
            <Switch id="notify-email" checked={notifyEmail} onCheckedChange={setNotifyEmail} />
          </div>
          <div className="flex items-center justify-between gap-4">
            <Label htmlFor="stall-days" className="flex-col items-start gap-1">
              <span>Haunt after</span>
              <span className="text-xs font-normal text-muted-foreground">Days without a commit</span>
            </Label>
            <Input
              id="stall-days"
              type="number"
              min={1}
              max={90}
              value={stallDays}
              onChange={(e) => setStallDays(Number(e.target.value))}
              className="w-20"
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={save} disabled={saving || stallDays < 1 || stallDays > 90}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
