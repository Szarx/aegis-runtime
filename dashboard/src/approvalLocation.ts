import { validTraceId } from './domain'
import { readTraceLocation, traceHash } from './traceLocation'

const reviewed = '#/reviewed-actions'

export function reviewActionLink(action: unknown, returnTo?: string): string | undefined {
  if (typeof action !== 'string' || !validTraceId(action)) return
  const trace = returnTo ? readTraceLocation(returnTo) : undefined
  const back = trace && traceHash(trace.traceId, trace.spanId, trace.returnTo)
  return reviewed + '?action_id=' + action + (back ? '&return=' + encodeURIComponent(back) : '')
}

export function readReviewLocation(hash: string): { actionId?: string; returnTo?: string } | null {
  if (hash === reviewed) return {}
  if (hash.length > 32768) return null
  const match = /^#\/reviewed-actions\?action_id=([0-9a-f]{32})(?:&return=([^&]+))?$/.exec(hash)
  if (!match?.[1] || !validTraceId(match[1])) return null
  if (!match[2]) return { actionId: match[1] }
  try {
    const trace = readTraceLocation(decodeURIComponent(match[2]))
    return trace ? { actionId: match[1], returnTo: traceHash(trace.traceId, trace.spanId, trace.returnTo) } : null
  } catch { return null }
}
