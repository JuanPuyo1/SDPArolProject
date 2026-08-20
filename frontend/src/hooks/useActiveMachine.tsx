import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  clearMachineFocus,
  loadMachineFocus,
  saveMachineFocus,
  type FocusSource,
  type MachineFocus,
} from '../api/machineFocus'
import type { Machine } from '../types/machine'
import { useAuth } from './useAuth'

type ActiveMachineContextValue = {
  focus: MachineFocus | null
  ready: boolean
  setFocusFromMachine: (machine: Machine, source: FocusSource) => void
  clearFocus: () => void
}

const ActiveMachineContext = createContext<ActiveMachineContextValue | null>(null)

export function ActiveMachineProvider({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const [focus, setFocus] = useState<MachineFocus | null>(null)
  const [focusUser, setFocusUser] = useState<string | null>(null)

  if (!loading && user && focusUser !== user.username) {
    setFocusUser(user.username)
    setFocus(loadMachineFocus(user.username))
  }
  if (!loading && !user && focusUser !== null) {
    setFocusUser(null)
    setFocus(null)
  }

  const setFocusFromMachine = useCallback(
    (machine: Machine, source: FocusSource) => {
      const next: MachineFocus = {
        serialNumber: machine.serialNumber,
        machineId: machine.machineId,
        source,
      }
      setFocus(next)
      if (user) saveMachineFocus(user.username, next)
    },
    [user],
  )

  const clearFocus = useCallback(() => {
    setFocus(null)
    if (user) clearMachineFocus(user.username)
  }, [user])

  const ready = !loading && (user ? focusUser === user.username : focusUser === null)

  const value = useMemo(
    () => ({
      focus,
      ready,
      setFocusFromMachine,
      clearFocus,
    }),
    [focus, ready, setFocusFromMachine, clearFocus],
  )

  return (
    <ActiveMachineContext.Provider value={value}>{children}</ActiveMachineContext.Provider>
  )
}

export function useActiveMachine() {
  const context = useContext(ActiveMachineContext)
  if (!context) {
    throw new Error('useActiveMachine must be used within ActiveMachineProvider')
  }
  return context
}
