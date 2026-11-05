import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, QueryChannel } from '../src/api/client'

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })
describe('AC-302 / AC-306 bounded, isolated query channels', () => {
  it('calls the browser fetch function without binding the channel as its receiver', async () => {
    const nativeLikeFetch = vi.fn(function(this: unknown) { if (this && this !== globalThis) throw new TypeError('Illegal invocation'); return Promise.resolve(new Response('{}')) })
    vi.stubGlobal('fetch', nativeLikeFetch)
    const channel = new QueryChannel(), commit = vi.fn()
    expect(await channel.run('/api/v1/traces', '', JSON.parse, commit)).toBe(true)
    expect(commit).toHaveBeenCalledExactlyOnceWith({})
  })
  it('commits the newest query even if an aborted older transport resolves later', async () => {
    const pending: ((response: Response) => void)[] = []
    const fetcher = vi.fn(() => new Promise<Response>(resolve => pending.push(resolve)))
    const channel = new QueryChannel(fetcher as typeof fetch)
    const commit = vi.fn()
    const old = channel.run('/api/v1/traces?offset=0', 'old-secret', JSON.parse, commit)
    const latest = channel.run('/api/v1/traces?offset=20', 'new-secret', JSON.parse, commit)
    pending[1]!(new Response('{"page":2}')); expect(await latest).toBe(true)
    pending[0]!(new Response('{"page":1}')); expect(await old).toBe(false)
    expect(commit).toHaveBeenCalledExactlyOnceWith({ page: 2 })
  })
  it('cancels an old connection and never places credentials in URL or cookies', async () => {
    let resolve!: (response: Response) => void
    const fetcher = vi.fn((_path: string, _options: RequestInit) => new Promise<Response>(done => { resolve = done }))
    const channel = new QueryChannel(fetcher as typeof fetch), commit = vi.fn()
    const query = channel.run('/api/v1/traces', 'test-secret', JSON.parse, commit)
    channel.cancel(); resolve(new Response('{}'))
    expect(await query).toBe(false); expect(commit).not.toHaveBeenCalled()
    const [path, options] = fetcher.mock.calls[0]!
    expect(path).not.toContain('secret')
    expect(options.headers).toEqual({ Authorization: 'Bearer test-secret' })
    expect(options.credentials).toBe('omit'); expect(options.redirect).toBe('error'); expect(options.cache).toBe('no-store')
  })
  it.each([[401, 'auth'], [404, 'missing'], [503, 'server']])('maps HTTP %s to a fixed safe error', async (code, kind) => {
    const channel = new QueryChannel(vi.fn(async () => new Response('private-db-password', { status: Number(code) })) as typeof fetch)
    const query = channel.run('/api/v1/traces', '', JSON.parse, vi.fn())
    await expect(query).rejects.toMatchObject({ kind })
    await expect(query).rejects.not.toThrow('private-db-password')
  })
  it('aborts on deadline and reports a fixed timeout', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn((_path: string, options?: RequestInit) => new Promise<Response>((_resolve, reject) => options?.signal?.addEventListener('abort', () => reject(new Error('transport aborted')))))
    const channel = new QueryChannel(fetcher as typeof fetch, 10)
    const check = expect(channel.run('/api/v1/traces', '', JSON.parse, vi.fn())).rejects.toMatchObject({ kind: 'timeout' })
    await vi.advanceTimersByTimeAsync(11); await check
  })
  it('blocks cross-origin paths and hides transport diagnostics', async () => {
    const fetcher = vi.fn(async () => { throw new Error('sensitive network diagnostics') })
    const channel = new QueryChannel(fetcher as typeof fetch)
    await expect(channel.run('https://other.example/api/v1/traces', 'secret', JSON.parse, vi.fn())).rejects.toBeInstanceOf(ApiError)
    expect(fetcher).not.toHaveBeenCalled()
    await expect(channel.run('/api/v1/traces', 'secret', JSON.parse, vi.fn())).rejects.toMatchObject({ kind: 'network' })
  })
})
