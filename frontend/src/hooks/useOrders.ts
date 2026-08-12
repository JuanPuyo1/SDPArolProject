import { useEffect, useState } from 'react'
import { fetchOrders } from '../api/orders'
import type { Order } from '../types/order'

export function useOrders() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchOrders()
        if (active) setOrders(data)
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Failed to load orders')
          setOrders([])
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

  return { orders, loading, error }
}
