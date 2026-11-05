import { stringify } from 'lossless-json'
import { decodeSecurity, securityEventFields, type SecurityList } from './api/security'

export type SecurityExportFormat = 'jsonl' | 'csv'

function csvCell(value: unknown): string {
  let text = value === null ? '' : String(value)
  if (/^[\u0000-\u001f]/u.test(text) || /^[\s\uFEFF]*[=+\-@＝＋－＠]/u.test(text)) text = "'" + text
  return '"' + text.replaceAll('"', '""') + '"'
}

export function securityPageFile(listing: SecurityList, format: SecurityExportFormat, now = new Date()) {
  if (!['jsonl','csv'].includes(format) || !Number.isFinite(now.getTime()) || !listing.items.length) throw new Error('Invalid page export')
  const rows = listing.items.map(event => Object.fromEntries(securityEventFields.map(key => [key,event[key]])))
  // Reuse the API contract on the explicit projection; unknown properties never enter either file.
  const page = decodeSecurity(stringify({ ...listing, items: rows })!)
  const body = format === 'jsonl'
    ? rows.map(row => stringify(row)).join('\n') + '\n'
    : [securityEventFields.map(csvCell).join(','), ...rows.map(row => securityEventFields.map(key => csvCell(row[key])).join(','))].join('\r\n') + '\r\n'
  return {
    filename: `aegis-security-page-offset-${page.offset}-count-${page.items.length}-${now.toISOString().replace(/[:.]/g,'-')}.${format}`,
    mime: format === 'jsonl' ? 'application/x-ndjson;charset=utf-8' : 'text/csv;charset=utf-8', body,
  }
}
