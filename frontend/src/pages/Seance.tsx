import { ArrowLeft, Lock, RefreshCw, Send } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import { BanishDialog } from '@/components/BanishDialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import {
  api,
  daysSince,
  errorMessage,
  formatDate,
  type Me,
  type Message,
  type Note,
  type SyncResult,
  type TrackedRepo,
} from '@/lib/api'
import { paragraphs } from '@/lib/text'

const SUGGESTIONS = ['Where was I?', 'What was I stuck on?', 'What should I do next?']

export function Seance({ me }: { me: Me }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const [repo, setRepo] = useState<TrackedRepo | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [notes, setNotes] = useState<Note[]>([])
  const [draft, setDraft] = useState('')
  const [noteDraft, setNoteDraft] = useState('')
  const [asking, setAsking] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [savingNote, setSavingNote] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    Promise.all([
      api<TrackedRepo>(`/api/repos/${id}`),
      api<Message[]>(`/api/repos/${id}/messages`),
      api<Note[]>(`/api/repos/${id}/notes`),
    ])
      .then(([r, m, n]) => {
        setRepo(r)
        setMessages(m)
        setNotes(n)
      })
      .catch((err) => {
        toast.error(errorMessage(err))
        navigate('/')
      })
  }, [id, navigate])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [messages, asking])

  async function ask(text: string) {
    const content = text.trim()
    if (!content || asking) return
    // Show the question immediately (optimistic UI); the ghost's answer follows.
    const pending: Message = { id: -Date.now(), role: 'user', content, created_at: new Date().toISOString() }
    setMessages((prev) => [...prev, pending])
    setDraft('')
    setAsking(true)
    try {
      const reply = await api<Message>(`/api/repos/${id}/chat`, { method: 'POST', body: { message: content } })
      setMessages((prev) => [...prev, reply])
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== pending.id))
      setDraft(content)
      toast.error(errorMessage(err))
    } finally {
      setAsking(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    ask(draft)
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      ask(draft)
    }
  }

  async function sync() {
    setSyncing(true)
    try {
      const result = await api<SyncResult>(`/api/repos/${id}/sync`, { method: 'POST' })
      toast.success(
        result.new_commits ? `The ghost remembered ${result.new_commits} new commits.` : 'No new commits since last time.',
      )
      setRepo(await api<TrackedRepo>(`/api/repos/${id}`))
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSyncing(false)
    }
  }

  async function addNote(e: FormEvent) {
    e.preventDefault()
    if (!noteDraft.trim()) return
    setSavingNote(true)
    try {
      const note = await api<Note>(`/api/repos/${id}/notes`, { method: 'POST', body: { content: noteDraft.trim() } })
      setNotes((prev) => [note, ...prev])
      setNoteDraft('')
      toast.success('The ghost will remember that.')
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setSavingNote(false)
    }
  }

  async function banish() {
    try {
      await api(`/api/repos/${id}`, { method: 'DELETE' })
    } catch (err) {
      toast.error(errorMessage(err))
      throw err // keep the dialog open so the user can retry
    }
    toast.success('The ghost has been laid to rest.')
    navigate('/')
  }

  if (!repo) return null
  const days = daysSince(repo.last_commit_at)
  const stalled = days !== null && days >= me.stall_days

  return (
    <main>
      <Link to="/" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> All ghosts
      </Link>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 font-serif text-4xl font-semibold">
            {repo.full_name.split('/')[1]}
            {repo.is_private && <Lock className="size-5 text-muted-foreground" aria-label="private" />}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {repo.full_name}
            {repo.last_synced_at && !repo.last_commit_at && ' · never awakened (no commits yet)'}
            {days !== null && (
              <>
                {' · '}
                <span className={stalled ? 'font-medium text-candle' : undefined}>
                  {days === 0 ? 'committed today' : `silent for ${days} days`}
                </span>
              </>
            )}
          </p>
        </div>
        <Button variant="outline" onClick={sync} disabled={syncing}>
          <RefreshCw className={syncing ? 'animate-spin' : undefined} />
          {syncing ? 'Gathering memories...' : 'Gather new memories'}
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Card className="flex min-h-[60vh] flex-col">
          <CardContent className="flex flex-1 flex-col">
            <div className="flex-1 space-y-5 overflow-y-auto pb-4" style={{ maxHeight: '60vh' }}>
              {messages.length === 0 && !asking && (
                <div className="py-12 text-center">
                  <div className="animate-float text-5xl" aria-hidden>
                    👻
                  </div>
                  <p className="ghost-voice mt-4 text-muted-foreground">The ghost is listening. Ask it something.</p>
                  <div className="mt-6 flex flex-wrap justify-center gap-2">
                    {SUGGESTIONS.map((s) => (
                      <Button key={s} variant="outline" size="sm" onClick={() => ask(s)}>
                        {s}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((m) =>
                m.role === 'user' ? (
                  <div key={m.id} className="flex justify-end">
                    <p className="max-w-[80%] rounded-2xl rounded-br-sm bg-secondary px-4 py-2 text-sm">{m.content}</p>
                  </div>
                ) : (
                  <div key={m.id} className="flex gap-3 animate-in fade-in slide-in-from-bottom-2 duration-700">
                    <span className="mt-1 text-xl" aria-hidden>
                      👻
                    </span>
                    <div className="ghost-voice max-w-[85%] space-y-3">
                      {paragraphs(m.content).map((p, i) => (
                        <p key={i} className="whitespace-pre-line">
                          {p}
                        </p>
                      ))}
                    </div>
                  </div>
                ),
              )}
              {asking && (
                <div className="flex gap-3">
                  <span className="text-xl" aria-hidden>
                    👻
                  </span>
                  <p className="ghost-voice animate-pulse text-muted-foreground italic">The ghost stirs...</p>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
            <form onSubmit={onSubmit} className="flex items-end gap-2 border-t pt-4">
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Speak to the ghost..."
                rows={2}
                className="resize-none"
              />
              <Button type="submit" size="icon" disabled={asking || !draft.trim()} aria-label="Send">
                <Send />
              </Button>
            </form>
          </CardContent>
        </Card>

        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Parking notes</CardTitle>
              <CardDescription>Stopping for now? Tell the ghost why, so it can remind you later.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form onSubmit={addNote} className="space-y-2">
                <Textarea
                  value={noteDraft}
                  onChange={(e) => setNoteDraft(e.target.value)}
                  placeholder="e.g. stuck on the OAuth redirect, try the ngrok URL next"
                  rows={3}
                  maxLength={500}
                />
                <Button type="submit" size="sm" className="w-full" disabled={savingNote || !noteDraft.trim()}>
                  {savingNote ? 'Whispering...' : 'Leave a note'}
                </Button>
              </form>
              <ul className="space-y-3">
                {notes.map((n) => (
                  <li key={n.id} className="border-l-2 border-primary/40 pl-3">
                    <p className="text-sm">{n.content}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{formatDate(n.created_at)}</p>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <BanishDialog repoName={repo.full_name} onBanish={banish} />
        </aside>
      </div>
    </main>
  )
}
