import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError, daysSince, errorMessage, RECONNECT_EVENT } from './api'

// A fresh Response per call: a body can only be read once.
function respond(status: number, body?: unknown) {
  return vi.fn().mockImplementation(
    async () =>
      new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
  )
}

// Caught values are `unknown` (anything can be thrown); these tests expect ApiError.
const failure = (p: Promise<unknown>) => p.catch((e: unknown) => e) as Promise<ApiError>

describe('api()', () => {
  let events: EventTarget

  beforeEach(() => {
    events = new EventTarget()
    vi.stubGlobal('window', events)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('returns parsed JSON on success', async () => {
    vi.stubGlobal('fetch', respond(200, { login: 'alice' }))
    await expect(api('/api/me')).resolves.toEqual({ login: 'alice' })
  })

  it('handles 204 No Content without parsing a body', async () => {
    vi.stubGlobal('fetch', respond(204))
    await expect(api('/api/repos/1', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('sends JSON only when there is a body', async () => {
    const fetchMock = respond(200, {})
    vi.stubGlobal('fetch', fetchMock)
    await api('/api/repos', { method: 'POST', body: { full_name: 'a/b' } })
    await api('/api/me')
    const [, withBody] = fetchMock.mock.calls[0]
    const [, withoutBody] = fetchMock.mock.calls[1]
    expect(withBody.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(withBody.body).toBe('{"full_name":"a/b"}')
    expect(withoutBody.headers).toBeUndefined()
  })

  it('throws ApiError with the server detail', async () => {
    vi.stubGlobal('fetch', respond(429, { detail: 'The spirits need rest.' }))
    const err = await failure(api('/api/x'))
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(429)
    expect(err.detail).toBe('The spirits need rest.')
  })

  it('asks for a GitHub reconnect only when the token was rejected', async () => {
    const reconnect = vi.fn()
    events.addEventListener(RECONNECT_EVENT, reconnect)

    vi.stubGlobal('fetch', respond(401, { detail: 'Not logged in' }))
    await api('/api/me').catch(() => {})
    expect(reconnect).not.toHaveBeenCalled()

    vi.stubGlobal('fetch', respond(401, { detail: 'github_reconnect' }))
    await api('/api/github/repos').catch(() => {})
    expect(reconnect).toHaveBeenCalledOnce()
  })

  it('survives a non-JSON error body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>Bad Gateway</html>', { status: 502, statusText: 'Bad Gateway' })))
    const err = await failure(api('/api/x'))
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(502)
  })
})

describe('errorMessage()', () => {
  it('turns the reconnect code into a human message', () => {
    expect(errorMessage(new ApiError(401, 'github_reconnect'))).toBe('Your GitHub connection expired.')
  })
  it('uses the error message otherwise', () => {
    expect(errorMessage(new ApiError(502, 'The ghost is unreachable'))).toBe('The ghost is unreachable')
    expect(errorMessage('weird')).toBe('Something went wrong')
  })
})

describe('daysSince()', () => {
  it('counts whole days and tolerates missing dates', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-30T12:00:00Z'))
    expect(daysSince('2026-10-20T12:00:00Z')).toBe(10)
    expect(daysSince('2026-10-30T01:00:00Z')).toBe(0)
    expect(daysSince(null)).toBeNull()
    vi.useRealTimers()
  })
})
