import type { Span } from './api/types'

export interface UsageAxis { total: bigint | null; known: number }
export interface TraceUsage { calls: number; input: UsageAxis; output: UsageAxis }

/** Coverage is relative to received model spans, never a billing guarantee. */
export function summarizeUsage(spans: Span[], traceId: string): TraceUsage {
  const models = new Map<string, Span>()
  for (const span of spans) {
    if (span.trace_id === traceId && span.operation === 'chat' && span.kind === 'CLIENT' && span.attributes['aegis.mapping.version'] === 'aegis.genai.v2') {
      if (!models.has(span.span_id)) models.set(span.span_id, span)
    }
  }
  function axis(key: string): UsageAxis {
    let total = 0n, known = 0
    for (const span of models.values()) {
      const value = span.attributes[key]
      if (typeof value === 'bigint' && value >= 0n && value <= 9223372036854775807n) { total += value; known++ }
    }
    return { total: models.size > 0 && known === models.size ? total : null, known }
  }
  return { calls: models.size, input: axis('gen_ai.usage.input_tokens'), output: axis('gen_ai.usage.output_tokens') }
}
