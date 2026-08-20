import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './hooks/useAuth'
import { ActiveMachineProvider } from './hooks/useActiveMachine'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ActiveMachineProvider>
          <App />
        </ActiveMachineProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
