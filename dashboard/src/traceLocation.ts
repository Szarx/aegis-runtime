import { validTraceId } from './domain'
import { queryHash, readQueryLocation } from './queryLocation'

const validSpanId = (value: string) => /^[0-9a-f]{16}$/.test(value) && !/^0+$/.test(value)
export interface TraceLocation { traceId: string; spanId?: string; returnTo?: string }

function returnQuery(value: string): string {
  const location = readQueryLocation(value)
  if (!location) throw new Error('Invalid return query')
  return queryHash(location.page,location.filters,location.offset)
}

export function readTraceLocation(hash: string): TraceLocation | null {
  try {
    if (hash.length > 16384) return null
    const match = /^#\/traces\/([0-9a-f]{32})(?:\?(.+))?$/.exec(hash)
    if (!match || !validTraceId(match[1]!)) return null
    const result: TraceLocation = {traceId:match[1]!}, seen = new Set<string>()
    for (const part of match[2]?.split('&') || []) {
      const pieces = part.split('=')
      if (pieces.length !== 2) return null
      const [key,value] = pieces as [string,string]
      if (seen.has(key) || !value) return null
      seen.add(key)
      if (key === 'span' && validSpanId(value)) result.spanId = value
      else if (key === 'return') result.returnTo = returnQuery(decodeURIComponent(value))
      else return null
    }
    return result
  } catch { return null }
}
export function traceHash(traceId: string, spanId?: string, returnTo?: string): string {
  if (!validTraceId(traceId) || (spanId !== undefined && !validSpanId(spanId))) throw new Error('Invalid node address')
  const params = [ ...(spanId === undefined ? [] : ['span=' + spanId]), ...(returnTo === undefined ? [] : ['return=' + encodeURIComponent(returnQuery(returnTo))]) ]
  const hash = '#/traces/' + traceId + (params.length ? '?' + params.join('&') : '')
  if (hash.length > 16384) throw new Error('Invalid node address')
  return hash
}
export function traceReturn(returnTo?: string): { href: string; label: string } {
  const href = returnTo === undefined ? '#/traces' : returnQuery(returnTo)
  return {href,label:href.startsWith('#/security-events') ? '返回安全事件' : '返回执行追踪'}
}
export function traceChanged(previousHash: string, nextHash: string): boolean {
  return readTraceLocation(previousHash)?.traceId !== readTraceLocation(nextHash)?.traceId
}
export function traceNodeLink(pageUrl: string, traceId: string, spanId: string): string {
  const url = new URL(pageUrl)
  if (!['http:','https:'].includes(url.protocol)) throw new Error('Invalid page address')
  url.username = ''; url.password = ''; url.search = ''; url.hash = traceHash(traceId,spanId)
  return url.toString()
}
