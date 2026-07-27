import { useEffect, useState } from 'react'
import { fetchDefaultMachine } from '../api/machines'
import type { Machine } from '../types/machine'

type UseMachineResult = {
  machine: Machine | null
  loading: boolean
  error: string | null
  reload: () => void
}

export function useDefaultMachine(): UseMachineResult {
  const [machine, setMachine] = useState<Machine | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    fetchDefaultMachine()
      .then((data) => {
        if (active) setMachine(data)
      })
      .catch((err: unknown) => {
        if (active) {
          setMachine(null)
          setError(err instanceof Error ? err.message : 'Failed to load machine')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [reloadToken])

  return {
    machine,
    loading,
    error,
    reload: () => setReloadToken((n) => n + 1),
  }
}
