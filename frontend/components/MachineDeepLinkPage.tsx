import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { fetchMachine } from '../src/api/machines'
import { useActiveMachine } from '../src/hooks/useActiveMachine'

export default function MachineDeepLinkPage() {
  const { id } = useParams<{ id: string }>()
  const { setFocusFromMachine } = useActiveMachine()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) {
      setError('Missing machine identifier.')
      return
    }

    let active = true
    fetchMachine(id)
      .then((machine) => {
        if (!active) return
        setFocusFromMachine(machine, 'link')
        const from = (location.state as { from?: string } | null)?.from
        const next =
          from && from !== `/m/${id}` && !from.startsWith('/select') && from !== '/scan'
            ? from
            : '/machine'
        navigate(next, { replace: true })
      })
      .catch((err: unknown) => {
        if (!active) return
        setError(err instanceof Error ? err.message : 'Could not open this machine.')
      })

    return () => {
      active = false
    }
  }, [id, location.state, navigate, setFocusFromMachine])

  return (
    <div className="page-loading">
      <p>{error ?? 'Opening machine…'}</p>
    </div>
  )
}
