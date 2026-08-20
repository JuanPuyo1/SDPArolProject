import { Route, Routes, Navigate } from 'react-router-dom'
import NavBar from '../components/NavBar'
import MachineInfoPage from '../components/MachineInfoPage'
import ManualPage from '../components/ManualPage'
import ChatbotPage from '../components/ChatbotPage'
import WelcomePage from '../components/WelcomePage'
import ProfilePage from '../components/ProfilePage'
import OrdersPage from '../components/OrdersPage'
import MaintenanceTicketsPage from '../components/MaintenanceTicketsPage'
import SelectMachinePage from '../components/SelectMachinePage'
import ScanQrPage from '../components/ScanQrPage'
import MachineDeepLinkPage from '../components/MachineDeepLinkPage'
import ProtectedRoute from '../components/ProtectedRoute'
import RequireMachineRoute, { MachineFocusGate } from '../components/RequireMachineRoute'
import VisibilityRoute from '../components/VisibilityRoute'
import { useAuth } from './hooks/useAuth'
import './App.css'

function AppShell() {
  const { user, loading } = useAuth()

  return (
    <>
      {!loading && user && <NavBar />}
      <main className="app-main">
        <Routes>
          <Route path="/" element={<WelcomePage />} />
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route
            path="/select"
            element={
              <ProtectedRoute>
                <SelectMachinePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/scan"
            element={
              <ProtectedRoute>
                <ScanQrPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/m/:id"
            element={
              <ProtectedRoute>
                <MachineDeepLinkPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/machine"
            element={
              <RequireMachineRoute>
                <MachineInfoPage />
              </RequireMachineRoute>
            }
          />
          <Route
            path="/manual"
            element={
              <RequireMachineRoute>
                <ManualPage />
              </RequireMachineRoute>
            }
          />
          <Route
            path="/orders"
            element={
              <VisibilityRoute allowed={['full', 'commercial']}>
                <MachineFocusGate>
                  <OrdersPage />
                </MachineFocusGate>
              </VisibilityRoute>
            }
          />
          <Route
            path="/maintenance"
            element={
              <VisibilityRoute allowed={['full', 'technician']}>
                <MachineFocusGate>
                  <MaintenanceTicketsPage />
                </MachineFocusGate>
              </VisibilityRoute>
            }
          />
          <Route
            path="/chatbot"
            element={
              <RequireMachineRoute>
                <ChatbotPage />
              </RequireMachineRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </>
  )
}

export default function App() {
  return <AppShell />
}
