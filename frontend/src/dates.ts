export const localTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'

export function localInputDate(date: string | Date) {
  const value = typeof date === 'string' ? new Date(date) : date
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`
}

// A wall-clock time may identify zero instants (spring forward), or two (fall back).
// Check the actual browser timezone offsets surrounding the date, then round-trip
// each candidate. Never silently normalize a nonexistent local time.
export function localDateCandidates(value: string): Date[] {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return []
  const [year, month, day, hour, minute] = value.split(/[-T:]/).map(Number)
  const wallTime = Date.UTC(year, month - 1, day, hour, minute)
  const offsets = new Set<number>()
  for (let hours = -48; hours <= 48; hours += 6) offsets.add(new Date(wallTime + hours * 3_600_000).getTimezoneOffset())
  return [...offsets].map(offset => new Date(wallTime + offset * 60_000))
    .filter(date => localInputDate(date) === value).sort((a, b) => a.getTime() - b.getTime())
}

export function formatExamDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function timezoneOffsetLabel(date: Date) {
  const offset = -date.getTimezoneOffset()
  return `UTC${offset >= 0 ? '+' : '-'}${String(Math.floor(Math.abs(offset) / 60)).padStart(2, '0')}:${String(Math.abs(offset) % 60).padStart(2, '0')}`
}
