import { useEffect, useState } from 'react'
import { fetchMaintenanceTickets } from '../api/tickets'
import type { MaintenanceTicket } from '../types/ticket'

export function useMaintenanceTickets() {
  const [tickets, setTickets] = useState<MaintenanceTicket[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchMaintenanceTickets()
        if (active) setTickets(data)
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Failed to load tickets')
          setTickets([])
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [])

  return { tickets, loading, error }
}
