import { BellRing, GitCommitHorizontal, NotebookPen } from 'lucide-react'

import { Button } from '@/components/ui/button'

const FEATURES = [
  {
    icon: GitCommitHorizontal,
    title: 'It remembers your work',
    text: 'Your commits and diffs are distilled into memories, so the ghost knows what you built and where you stopped.',
  },
  {
    icon: NotebookPen,
    title: 'It keeps your parking notes',
    text: 'Leave one line when you stop ("stuck on the OAuth redirect"). Weeks later, the ghost hands it back.',
  },
  {
    icon: BellRing,
    title: 'It haunts you when you stall',
    text: 'Go quiet for too long and the ghost reaches out with a reminder and one small step to get you going.',
  },
]

export function Landing() {
  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col items-center justify-center px-6 py-16 text-center">
      <div className="animate-float mb-6 text-7xl" aria-hidden>
        👻
      </div>
      <h1 className="font-serif text-5xl font-semibold tracking-tight sm:text-6xl">GhostCommit</h1>
      <p className="ghost-voice mt-4 max-w-xl text-muted-foreground">
        Every abandoned side project leaves a ghost behind. Summon it, and it will tell you exactly where you left
        off.
      </p>
      {/* A full-page navigation, not fetch: OAuth needs the browser itself to visit GitHub. */}
      <Button asChild size="lg" className="mt-8">
        <a href="/auth/github/login">Summon with GitHub</a>
      </Button>

      <section className="mt-16 grid gap-6 text-left sm:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <div key={title} className="rounded-xl border bg-card/60 p-5">
            <Icon className="mb-3 size-5 text-primary" />
            <h2 className="font-medium">{title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{text}</p>
          </div>
        ))}
      </section>

      <p className="mt-12 text-xs text-muted-foreground">
        Memory by Backboard · Spoken by Gemma, an open-weight model · Hosted on Render
      </p>
    </main>
  )
}
