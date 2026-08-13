import { useEffect, useState } from 'react'
import { fetchDefaultMachine, fetchMachine, fetchMachines } from '../api/machines'
import type { Machine, MachineSummary } from '../types/machine'

type UseMachineResult = {
  machine: Machine | null
  loading: boolean
  error: string | null
  reload: () => void
}

export function useMachines(): {
  machines: MachineSummary[]
  loading: boolean
  error: string | null
} {
  const [machines, setMachines] = useState<MachineSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    fetchMachines()
      .then((data) => {
        if (active) setMachines(data)
      })
      .catch((err: unknown) => {
        if (active) {
          setMachines([])
          setError(err instanceof Error ? err.message : 'Failed to load machines')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  return { machines, loading, error }
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

export function useMachine(serialNumber: string | null): UseMachineResult {
  const [machine, setMachine] = useState<Machine | null>(null)
  const [loading, setLoading] = useState(Boolean(serialNumber))
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    if (!serialNumber) {
      setMachine(null)
      setLoading(false)
      setError(null)
      return undefined
    }

    let active = true
    setLoading(true)
    setError(null)

    fetchMachine(serialNumber)
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
  }, [serialNumber, reloadToken])

  return {
    machine,
    loading,
    error,
    reload: () => setReloadToken((n) => n + 1),
  }
}
