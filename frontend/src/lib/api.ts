export type Me = {
  login: string
  name: string | null
  avatar_url: string | null
  email: string | null
  notify_email: boolean
  stall_days: number
}

export type TrackedRepo = {
  id: number
  full_name: string
  is_private: boolean
  last_commit_at: string | null
  last_synced_at: string | null
  last_haunted_at: string | null
}

export type GitHubRepo = {
  full_name: string
  description: string | null
  private: boolean
  pushed_at: string
  tracked: boolean
}

export type Note = { id: number; content: string; created_at: string }
export type Message = { id: number; role: 'user' | 'ghost'; content: string; created_at: string }
export type SyncResult = { new_commits: number; memory: string | null }
export type Haunting = {
  id: number
  repo_id: number
  repo: string
  message: string
  emailed: boolean
  read: boolean
  created_at: string
}

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

// Fired when GitHub rejected the stored token; the layout shows a "Reconnect GitHub" banner.
export const RECONNECT_EVENT = 'ghostcommit:reconnect'
// Fired after hauntings are marked read; the layout refreshes its unread badge.
export const HAUNTINGS_CHANGED_EVENT = 'ghostcommit:hauntings-changed'

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(path, {
    method: init.method ?? 'GET',
    headers: init.body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const detail = typeof data.detail === 'string' ? data.detail : res.statusText
    if (res.status === 401 && detail === 'github_reconnect') window.dispatchEvent(new Event(RECONNECT_EVENT))
    throw new ApiError(res.status, detail)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError && err.detail === 'github_reconnect') return 'Your GitHub connection expired.'
  return err instanceof Error ? err.message : 'Something went wrong'
}

export function daysSince(iso: string | null): number | null {
  if (!iso) return null
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
