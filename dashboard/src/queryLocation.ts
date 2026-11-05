import { emptyFilters, type Filters } from './api/types'
import { emptySecurityFilters, securityPath, type SecurityFilters } from './api/security'
import { listPath } from './domain'

export type QueryPage = 'traces' | 'security-events'
export interface QueryLocation { page: QueryPage; filters: Filters | SecurityFilters; offset: number }
const fields = {
  traces: ['agent','service','status','after','before'],
  'security-events': ['subject','tool','permission','service_name','action_id','trace_id','effect','outcome','after','before'],
} as const
const require = (value: unknown) => { if (!value) throw new Error('查询地址无效，请重新选择筛选条件。') }
const blank = (page: QueryPage) => page === 'traces' ? emptyFilters() : emptySecurityFilters()

export function localTime(value: string): string {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0,-1)
}
export function queryDraft<T extends Filters | SecurityFilters>(filters: T): T {
  return {...filters, after:localTime(filters.after), before:localTime(filters.before)}
}
export function applyQueryDraft<T extends Filters | SecurityFilters>(draft: T, applied: T): T {
  const result = {...draft}
  for (const key of ['after','before'] as const) {
    if (draft[key] === localTime(applied[key])) result[key] = applied[key]
  }
  return result
}
export function queryHash(page: QueryPage, filters: Filters | SecurityFilters, offset: number): string {
  require(Number.isInteger(offset) && offset >= 0 && offset <= 10000 && offset % 20 === 0)
  require(Object.keys(filters).length === fields[page].length && fields[page].every(key => Object.hasOwn(filters,key)))
  const values = filters as unknown as Record<string,string>
  require(Object.values(values).every(value => typeof value === 'string' && value.length <= 128 && !/[\x00-\x1f\x7f\ufffd]/.test(value)))
  if (page === 'traces') {
    require(!values.status || ['UNSET','ERROR'].includes(values.status))
    require(['agent','service'].every(key => !values[key] || !!values[key]!.trim()))
    listPath(filters as Filters,offset)
  } else securityPath(filters as SecurityFilters,offset)
  const params = new URLSearchParams()
  for (const key of fields[page]) {
    let value = values[key]!
    if (!value) continue
    if (key === 'after' || key === 'before') value = new Date(value).toISOString()
    params.set(key,value)
  }
  if (offset) params.set('offset',String(offset))
  const hash = '#/' + page + (params.size ? '?' + params.toString() : '')
  require(hash.length <= 4096)
  return hash
}
export function readQueryLocation(hash: string): QueryLocation | null {
  try {
    require(hash.length <= 4096 && !/%(?![0-9a-fA-F]{2})/.test(hash))
    const match = /^#\/(traces|security-events)(?:\?(.+))?$/.exec(hash)
    require(match)
    const page = match![1] as QueryPage, filters = blank(page)
    const params = new URLSearchParams(match![2] || ''), seen = new Set<string>()
    for (const [key,value] of params) {
      require(!seen.has(key) && value && (key === 'offset' || (fields[page] as readonly string[]).includes(key)))
      seen.add(key)
      if (key !== 'offset') {
        if (key === 'after' || key === 'before') require(/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(value) && new Date(value).toISOString() === value)
        ;(filters as unknown as Record<string,string>)[key] = value
      }
    }
    const raw = params.get('offset') || '0'
    require(/^(0|[1-9][0-9]{0,4})$/.test(raw))
    const offset = Number(raw)
    queryHash(page,filters,offset)
    return {page,filters,offset}
  } catch { return null }
}
export function queryLink(pageUrl: string, page: QueryPage, filters: Filters | SecurityFilters, offset: number): string {
  const url = new URL(pageUrl)
  require(['http:','https:'].includes(url.protocol))
  url.username = ''; url.password = ''; url.search = ''; url.hash = queryHash(page,filters,offset)
  return url.toString()
}
