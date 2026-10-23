import { useCallback, useEffect, useState } from 'react'
import { request } from './api'

export function useData<T>(path: string) {
  const [version, setVersion] = useState(0)
  const [result, setResult] = useState<{ path: string; version: number; data: T | null; error: string } | null>(null)
  useEffect(() => {
    let active = true
    request<T>(path).then(data => { if (active) setResult({ path, version, data, error: '' }) }).catch(e => { if (active) setResult({ path, version, data: null, error: e.message }) })
    return () => { active = false }
  }, [path, version])
  const reload = useCallback(() => setVersion(v => v + 1), [])
  const current = result?.path === path && result.version === version ? result : null
  return { data: current?.data ?? null, error: current?.error ?? '', loading: !current, reload }
}
